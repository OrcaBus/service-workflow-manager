from drf_spectacular.utils import extend_schema, extend_schema_view
from drf_spectacular.types import OpenApiTypes
from rest_framework.decorators import action
from rest_framework import mixins, status
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from django.db import transaction
from django.utils import timezone

from workflow_manager.models import State, WorkflowRun
from workflow_manager.serializers.state import (
    StateSerializer,
    StateCreateRequestSerializer,
    StateUpdateRequestSerializer,
    StateBatchTransitionRequestSerializer,
    StateBatchTransitionResponseSerializer,
)


class StateTransitionValidationMixin:
    """
    states_transition_validation_map for state creation, update
    Structure:
    - If value is a list: ['STATE1', 'STATE2'] means only these states can transition to the key
    - If value is a dict with 'excluded_states': allows all states except those listed
    - If value is a dict with 'allowed_states': same as list format

    refer:
        "Resolved" -- https://github.com/umccr/orcabus/issues/593
        "Deprecated" -- https://github.com/umccr/orcabus/issues/695
    """
    states_transition_validation_map = {
        'RESOLVED': ['FAILED'],  # Only FAILED can transition to RESOLVED
        'DEPRECATED': {'excluded_states': ['FAILED', 'ABORTED', 'RESOLVED', 'DEPRECATED']}  # All states except these can transition to DEPRECATED
    }

    @staticmethod
    def normalize_workflowrun_orcabus_id(orcabus_id: str) -> str:
        if orcabus_id.startswith("wfr."):
            return orcabus_id[4:]
        return orcabus_id

    def is_valid_next_state(self, current_status, request_status: str) -> bool:
        """
        Check if transitioning from current_status to request_status is valid.

        Uses states_transition_validation_map to determine validity:
        - If map entry is a list: only states in the list can transition
        - If map entry is a dict with 'excluded_states': all states except excluded ones can transition
        - If map entry is a dict with 'allowed_states': same as list format
        - If current_status is None (no state exists): only DEPRECATED is allowed
        """
        # Handle case when there's no current state - only allow DEPRECATED
        if current_status is None:
            return request_status.upper() == 'DEPRECATED'

        request_status_upper = request_status.upper()
        current_status_upper = current_status.upper()

        # Check if request_status is in the validation map
        if request_status_upper not in self.states_transition_validation_map:
            return False

        validation_rule = self.states_transition_validation_map[request_status_upper]

        # Handle dict format with 'excluded_states' or 'allowed_states'
        if isinstance(validation_rule, dict):
            if 'excluded_states' in validation_rule:
                # Allow all states except the excluded ones
                excluded_states = [s.upper() for s in validation_rule['excluded_states']]
                return current_status_upper not in excluded_states
            elif 'allowed_states' in validation_rule:
                # Only allow states in the allowed_states list
                allowed_states = [s.upper() for s in validation_rule['allowed_states']]
                return current_status_upper in allowed_states

        # Handle list format (backward compatibility and simpler format)
        if isinstance(validation_rule, list):
            allowed_states = [s.upper() for s in validation_rule]
            return current_status_upper in allowed_states

        return False


@extend_schema_view(
    create=extend_schema(
        request=StateCreateRequestSerializer,
        responses={201: StateSerializer},
        description=(
            "Create a state (body: status, comment; JSON uses camelCase per API settings)."
        ),
    ),
    partial_update=extend_schema(
        request=StateUpdateRequestSerializer,
        responses={200: StateSerializer},
        description=(
            "Update state comment only."
        ),
    )
)
class StateViewSet(StateTransitionValidationMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin,  GenericViewSet):
    serializer_class = StateSerializer
    search_fields = State.get_base_fields()
    http_method_names = ['get', 'post', 'patch']
    pagination_class = None
    lookup_value_regex = "[^/]+" # to allow id prefix

    def get_queryset(self):
        return State.objects.filter(workflow_run=self.kwargs["orcabus_id"])

    @extend_schema(responses=OpenApiTypes.OBJECT, description="Get states transition validation map")
    @action(detail=False, methods=['get'], url_name='get_states_transition_validation_map', url_path='get_states_transition_validation_map')
    def get_states_transition_validation_map(self, request, **kwargs):
        """
        Returns states transition validation map.
        """
        return Response(self.states_transition_validation_map)

    def create(self, request, *args, **kwargs):
        """
        Create a custom new state for a workflow run.
        Currently we support "Resolved", "Deprecated"
        """
        required_fields = {"status", "comment"}
        provided_fields = set(request.data.keys())

        if required_fields - provided_fields:
            return Response(
                {"detail": "status and comment fields are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        wfr_orcabus_id = self.kwargs.get("orcabus_id")
        workflow_run = WorkflowRun.objects.get(orcabus_id=wfr_orcabus_id)

        body = StateCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        vd = body.validated_data
        request_status = vd["status"].upper()
        request_comment = vd["comment"]

        latest_state = workflow_run.get_latest_state()
        # Handle case when there's no latest state - only allow DEPRECATED
        if not latest_state:
            if request_status != 'DEPRECATED':
                return Response({"detail": "No state found for workflow run '{}'. Only DEPRECATED is allowed when there are no states.".format(wfr_orcabus_id)},
                                status=status.HTTP_400_BAD_REQUEST)
            latest_status = None
        else:
            latest_status = latest_state.status
            # check if the state status is valid
            if not self.is_valid_next_state(latest_status, request_status):
                return Response({"detail": "Invalid state request. Can't add state '{}' to '{}'".format(request_status, latest_status)},
                                status=status.HTTP_400_BAD_REQUEST)

        instance = State.objects.create(
            workflow_run=workflow_run,
            status=request_status,
            timestamp=timezone.now(),
            comment=request_comment,
        )

        data = StateSerializer(instance).data
        headers = self.get_success_headers(data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        required_fields = {"comment"}
        provided_fields = set(request.data.keys())

        if required_fields - provided_fields:
            return Response(
                {"detail": "comment field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if the state being updated is in the validation map
        if instance.status not in self.states_transition_validation_map:
            return Response({"detail": "Invalid state status to update comment."},
                            status=status.HTTP_400_BAD_REQUEST)

        body = StateUpdateRequestSerializer(data=request.data, partial=partial)
        body.is_valid(raise_exception=True)
        vd = body.validated_data
        instance.comment = vd["comment"]
        instance.save(update_fields=["comment"])

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        data = StateSerializer(instance).data
        headers = self.get_success_headers(data)
        return Response(data, status=status.HTTP_200_OK, headers=headers)


@extend_schema_view(
    batch_state_transition=extend_schema(
        request=StateBatchTransitionRequestSerializer,
        responses={201: StateBatchTransitionResponseSerializer},
        description="Batch transition workflow runs to a target state.",
    )
)
class WorkflowRunBatchStateTransitionViewSet(StateTransitionValidationMixin, GenericViewSet):
    http_method_names = ['post']
    pagination_class = None

    @action(detail=False, methods=['post'], url_path='batch-state-transition')
    def batch_state_transition(self, request, *args, **kwargs):
        body = StateBatchTransitionRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        vd = body.validated_data

        workflowrun_orcabus_ids = vd["workflowrun_orcabus_ids"]
        request_status = vd["status"].upper()
        request_comment = vd["comment"]

        normalized_ids = [
            self.normalize_workflowrun_orcabus_id(orcabus_id)
            for orcabus_id in workflowrun_orcabus_ids
        ]
        workflow_runs = list(WorkflowRun.objects.filter(orcabus_id__in=normalized_ids))
        workflow_runs_by_normalized_id = {
            self.normalize_workflowrun_orcabus_id(wfr.orcabus_id): wfr for wfr in workflow_runs
        }
        missing_ids = [
            raw_id
            for raw_id, normalized_id in zip(workflowrun_orcabus_ids, normalized_ids)
            if normalized_id not in workflow_runs_by_normalized_id
        ]
        if missing_ids:
            return Response(
                {"detail": f"Workflow run(s) not found: {', '.join(missing_ids)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for wfr in workflow_runs:
            latest_state = wfr.get_latest_state()
            latest_status = latest_state.status if latest_state else None
            if not self.is_valid_next_state(latest_status, request_status):
                return Response(
                    {
                        "detail": "Invalid state request. Can't add state '{}' to workflow run '{}' from '{}'".format(
                            request_status,
                            wfr.orcabus_id,
                            latest_status,
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            for wfr in workflow_runs:
                State.objects.create(
                    workflow_run=wfr,
                    status=request_status,
                    timestamp=timezone.now(),
                    comment=request_comment,
                )

        summary = StateBatchTransitionResponseSerializer(
            instance={
                "created_count": len(workflow_runs),
                "workflowrun_orcabus_ids": [wfr.orcabus_id for wfr in workflow_runs],
            }
        )
        return Response(summary.data, status=status.HTTP_201_CREATED)
