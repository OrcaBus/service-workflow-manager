import json
import logging

from datetime import datetime, timezone

from django.contrib.postgres.aggregates import StringAgg
from django.db.models import F
from rest_framework import status
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from django.shortcuts import get_object_or_404

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, PolymorphicProxySerializer

from workflow_manager.aws_event_bridge.event import emit_wru_api_event
from workflow_manager.errors import RerunDuplicationError
from workflow_manager.models.utils import create_portal_run_id
from workflow_manager.models.comment import Comment
from workflow_manager.serializers.library import LibrarySerializer
from workflow_manager.serializers.payload import PayloadSerializer
from workflow_manager.serializers.workflow_run_action import AllowedRerunWorkflow, RERUN_INPUT_SERIALIZERS, \
    AllowedRerunWorkflowSerializer, RnasumRerunInputSerializer
from workflow_manager.models import (
    WorkflowRun,
    State,
)
from workflow_manager.viewsets.base import get_email_from_bearer_authorization


logger = logging.getLogger(__name__)

class WorkflowRunActionViewSet(ViewSet):
    lookup_value_regex = "[^/]+"  # to allow orcabus id prefix
    queryset = WorkflowRun.objects.prefetch_related('states').all()

    @extend_schema(responses=AllowedRerunWorkflowSerializer, description="Allowed rerun workflows")
    @action(detail=True, methods=['get'], url_name='validate_rerun_workflows', url_path='validate_rerun_workflows')
    def validate_rerun_workflows(self, request, *args, **kwargs):
        wfl_run = get_object_or_404(self.queryset, pk=kwargs.get('pk'))
        is_valid = wfl_run.workflow.name in [member.value for member in AllowedRerunWorkflow]

        # Get allowed dataset choice for the workflow
        wfl_name = wfl_run.workflow.name
        allowed_dataset_choice = []
        if wfl_name == AllowedRerunWorkflow.RNASUM.value:
            allowed_dataset_choice = RERUN_INPUT_SERIALIZERS[wfl_name].allowed_dataset_choice

        response = {
            'is_valid': is_valid,
            'allowed_dataset_choice': allowed_dataset_choice,
            'valid_workflows': [member.value for member in AllowedRerunWorkflow],
        }
        return Response(response, status=status.HTTP_200_OK)

    @extend_schema(
        request=RnasumRerunInputSerializer,
        responses=OpenApiTypes.OBJECT,
        description="Trigger a workflow run rerun by emitting an event to EventBridge with an overridden workflow "
                    "input payload. Current supported workflow: 'rnasum'"
    )
    @action(
        detail=True,
        methods=['post'],
        url_name='rerun',
        url_path='rerun'
    )
    def rerun(self, request, *args, **kwargs):
        """
        rerun from existing workflow run
        """
        pk = self.kwargs.get('pk')
        wfl_run = get_object_or_404(self.queryset, pk=pk)

        # Only approved workflow name is allowed
        if wfl_run.workflow.name not in [member.value for member in AllowedRerunWorkflow]:
            return Response(f"This workflow type is not allowed: {wfl_run.workflow.name}",
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = RERUN_INPUT_SERIALIZERS[wfl_run.workflow.name](data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        # Check if rerun is deprecated
        is_wfr_deprecated = wfl_run.states.filter(status='DEPRECATED').exists()
        if is_wfr_deprecated:
            return Response({"detail": "Workflow run has been deprecated and rerun is not allowed."},
                            status=status.HTTP_400_BAD_REQUEST)

        # User will be used to create rerun audit comment
        user_email = get_email_from_bearer_authorization(request)

        try:
            detail = construct_rerun_eb_detail(wfl_run, serializer.data)
            new_portal_run_id = detail.get("portalRunId")
        except RerunDuplicationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        emit_wru_api_event(detail)

        try:
            Comment.objects.create(
                workflow_run=wfl_run,
                created_by="workflow manager",
                text=f"Rerun of {wfl_run.portal_run_id} with new portal run id: {new_portal_run_id} by {user_email}",
            )
        except Exception as e:
            logger.exception("Failed to create rerun audit comment for workflow run %s, user email: %s, new portal run id: %s, error: %s", wfl_run.orcabus_id, user_email, new_portal_run_id, e)

        return Response(detail, status=status.HTTP_200_OK)


def construct_rerun_eb_detail(wfl_run: WorkflowRun, input_body: dict) -> dict:
    """
    Construct WorkflowRunUpdate event bridge detail for rerun based on the existing workflow run and request body.
    The returned dict conforms to the WorkflowRunUpdate (WRU) schema.
    """
    new_portal_run_id = create_portal_run_id()
    wfl_name = wfl_run.workflow.name

    # Each rerun workflow type must implement its own rerun duplication logic and raise `RerunDuplicationError`
    # if it is considered a duplication, unless `allow_duplication` is set to True in the input body.
    new_payload: dict
    if wfl_name == AllowedRerunWorkflow.RNASUM.value:
        new_payload = construct_rnasum_rerun_payload(wfl_run, input_body)
    else:
        raise ValueError(f"Rerun is not allowed for this workflow: {wfl_name}")

    # Replace references to the old portal_run_id within the payload data, since dynamic payload
    # fields (e.g. S3 paths) may still reference it.  Scoped to payload only to avoid corrupting
    # structured fields like orcabusId.
    old_portal_run_id = wfl_run.portal_run_id
    new_payload = json.loads(
        json.dumps(new_payload).replace(old_portal_run_id, new_portal_run_id)
    )

    workflow = wfl_run.workflow
    new_workflow_run_name = wfl_run.workflow_run_name.replace(
        old_portal_run_id,
        new_portal_run_id,
    )
    return {
        "status": "READY",
        "portalRunId": new_portal_run_id,
        "workflowRunName": new_workflow_run_name,
        "workflow": {
            "orcabusId": workflow.orcabus_id,
            "name": workflow.name,
            "version": workflow.version,
            "codeVersion": workflow.code_version,
            "executionEngine": workflow.execution_engine,
            "executionEnginePipelineId": workflow.execution_engine_pipeline_id,
        },
        "libraries": LibrarySerializer(wfl_run.libraries.all(), many=True, camel_case_data=True).data,
        "payload": new_payload,
        "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }


def construct_rnasum_rerun_payload(wfl_run: WorkflowRun, input_body: dict) -> dict:
    """
    Construct payload for rerun for 'rnasum' workflow based on the request body payload
    """
    allow_rerun_duplication = input_body.get("allow_duplication", False)

    if not allow_rerun_duplication:
        # The duplication check is based on the dataset input at the READY state of the workflow run that has the same
        # linked libraries and Workflow entity.
        # If the dataset has been run in the past, it will raise an error unless `allow_duplication` is set to True.
        library_ids = wfl_run.libraries.values_list('library_id', flat=True)
        sorted_library_ids = sorted(library_ids)
        library_ids_string = ','.join(sorted_library_ids)

        # Find all workflowrun that has the same linked libraries and Workflow entity
        wfl_runs = WorkflowRun.objects.annotate(
            library_ids=StringAgg('libraries__library_id', delimiter=',', ordering=F('libraries__library_id').asc())
        ).filter(
            workflow=wfl_run.workflow,
            library_ids=library_ids_string
        )
        past_dataset = set()
        for run in wfl_runs:
            try:
                # We will ignore deprecated runs
                is_wfr_run_deprecated = run.states.filter(status='DEPRECATED').exists()
                if is_wfr_run_deprecated:
                    continue

                # Get the payload where the state is 'READY'
                ready_state: State = run.states.get(status='READY')
                ready_data_payload = PayloadSerializer(ready_state.payload).data
                past_dataset.add(ready_data_payload.get('data', {}).get("inputs", {}).get("dataset", ''))
            except State.DoesNotExist:
                logger.warning("Workflow run %s has no READY state", run.orcabus_id)
                continue
        if input_body["dataset"] in past_dataset:
            raise RerunDuplicationError(f"Dataset '{input_body['dataset']}' has been run in the past. "
                                        f"Set 'allow_duplication' manually to True to proceed.")

    # Get the payload where the state is 'READY'
    ready_state: State = wfl_run.states.get(status='READY')
    ready_data_payload = PayloadSerializer(ready_state.payload).data

    new_data_payload = {
        'version': ready_data_payload['version'],
        'data': ready_data_payload['data']
    }

    # Override payload based on given input
    new_data_payload['data']["inputs"]["dataset"] = input_body["dataset"]

    return new_data_payload
