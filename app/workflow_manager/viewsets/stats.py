from collections import defaultdict

from django.db.models import Q, Max, F, Count
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from workflow_manager.models import WorkflowRun
from workflow_manager.models.analysis import Analysis, AnalysisStatus
from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager.models.workflow import Workflow, ValidationState
from workflow_manager.serializers.base import version_sort_key
from workflow_manager.serializers.stats import (
    WorkflowRunStatusCountSerializer,
    AnalysisRunStatusCountSerializer,
    WorkflowStatusCountSerializer,
    AnalysisStatusCountSerializer,
)

WORKFLOW_RUN_TERMINATION_STATUSES = ["FAILED", "ABORTED", "SUCCEEDED", "RESOLVED", "DEPRECATED"]
ANALYSIS_RUN_TERMINATION_STATUSES = ["FAILED", "ABORTED", "SUCCEEDED", "RESOLVED", "DEPRECATED"]


class StatsViewSet(GenericViewSet):
    """Read-only aggregate statistics for workflow runs, analysis runs, workflows, and analyses."""

    pagination_class = None
    http_method_names = ["get"]

    def _workflow_run_status_counts(self):
        """Count WorkflowRun records grouped by their latest State status."""
        qs = WorkflowRun.objects.annotate(latest_state_time=Max("states__timestamp"))

        all_count = qs.count()

        annotated = qs.filter(latest_state_time__isnull=False)

        succeeded = annotated.filter(states__timestamp=F("latest_state_time"), states__status="SUCCEEDED").count()
        aborted = annotated.filter(states__timestamp=F("latest_state_time"), states__status="ABORTED").count()
        failed = annotated.filter(states__timestamp=F("latest_state_time"), states__status="FAILED").count()
        resolved = annotated.filter(states__timestamp=F("latest_state_time"), states__status="RESOLVED").count()
        deprecated = annotated.filter(states__timestamp=F("latest_state_time"), states__status="DEPRECATED").count()
        ongoing = annotated.filter(
            Q(states__timestamp=F("latest_state_time"))
            & ~Q(states__status__in=WORKFLOW_RUN_TERMINATION_STATUSES)
        ).count()

        return {
            "all": all_count,
            "succeeded": succeeded,
            "aborted": aborted,
            "failed": failed,
            "resolved": resolved,
            "deprecated": deprecated,
            "ongoing": ongoing,
        }

    def _analysis_run_status_counts(self):
        """Count AnalysisRun records grouped by their latest AnalysisRunState status."""
        qs = AnalysisRun.objects.annotate(latest_state_time=Max("states__timestamp"))

        all_count = qs.count()

        annotated = qs.filter(latest_state_time__isnull=False)

        succeeded = annotated.filter(states__timestamp=F("latest_state_time"), states__status="SUCCEEDED").count()
        aborted = annotated.filter(states__timestamp=F("latest_state_time"), states__status="ABORTED").count()
        failed = annotated.filter(states__timestamp=F("latest_state_time"), states__status="FAILED").count()
        resolved = annotated.filter(states__timestamp=F("latest_state_time"), states__status="RESOLVED").count()
        deprecated = annotated.filter(states__timestamp=F("latest_state_time"), states__status="DEPRECATED").count()
        ongoing = annotated.filter(
            Q(states__timestamp=F("latest_state_time"))
            & ~Q(states__status__in=ANALYSIS_RUN_TERMINATION_STATUSES)
        ).count()

        return {
            "all": all_count,
            "succeeded": succeeded,
            "aborted": aborted,
            "failed": failed,
            "resolved": resolved,
            "deprecated": deprecated,
            "ongoing": ongoing,
        }

    @extend_schema(
        responses=WorkflowRunStatusCountSerializer,
        description="Counts of workflow runs grouped by latest state status.",
    )
    @action(detail=False, methods=["GET"], url_path="workflow_run/status_counts")
    def workflow_run_status_counts(self, request):
        return Response(self._workflow_run_status_counts(), status=200)

    @extend_schema(
        responses=AnalysisRunStatusCountSerializer,
        description="Counts of analysis runs grouped by latest state status.",
    )
    @action(detail=False, methods=["GET"], url_path="analysis_run/status_counts")
    def analysis_run_status_counts(self, request):
        return Response(self._analysis_run_status_counts(), status=200)

    @extend_schema(
        responses=WorkflowStatusCountSerializer,
        description="Counts of workflow definitions grouped by validation state.",
    )
    @action(detail=False, methods=["GET"], url_path="workflow/status_counts")
    def workflow_status_counts(self, request):
        counts = (
            Workflow.objects.values("validation_state")
            .annotate(count=Count("orcabus_id"))
            .order_by("validation_state")
        )
        result = {
            "all": Workflow.objects.count(),
            **{vs.value.lower(): 0 for vs in ValidationState},
        }
        for row in counts:
            key = row["validation_state"].lower()
            result[key] = row["count"]

        return Response(result, status=200)

    @extend_schema(
        responses=AnalysisStatusCountSerializer,
        description="Counts of analysis definitions grouped by status.",
    )
    @action(detail=False, methods=["GET"], url_path="analysis/status_counts")
    def analysis_status_counts(self, request):
        counts = (
            Analysis.objects.values("status")
            .annotate(count=Count("orcabus_id"))
            .order_by("status")
        )
        result = {
            "all": Analysis.objects.count(),
            **{s.value.lower(): 0 for s in AnalysisStatus},
        }
        for row in counts:
            key = row["status"].lower()
            result[key] = row["count"]

        return Response(result, status=200)

    @staticmethod
    def _get_latest_workflow_per_group():
        """Group workflows by name (case-insensitive), return only the latest version per group."""
        grouped: dict[str, list] = defaultdict(list)
        for w in Workflow.objects.all():
            grouped[w.name.lower()].append(w)

        latest_workflows = []
        for group in grouped.values():
            group.sort(key=lambda w: version_sort_key(w.version), reverse=True)
            latest_workflows.append(group[0])
        return latest_workflows

    @extend_schema(
        responses=WorkflowStatusCountSerializer,
        description=(
            "Counts of grouped workflows by validation state. "
            "Workflows are grouped by name and only the latest version per group is counted."
        ),
    )
    @action(detail=False, methods=["GET"], url_path="grouped_workflow/status_counts")
    def grouped_workflow_status_counts(self, request):
        latest_workflows = self._get_latest_workflow_per_group()

        result = {
            "all": len(latest_workflows),
            **{vs.value.lower(): 0 for vs in ValidationState},
        }
        for w in latest_workflows:
            key = w.validation_state.lower()
            if key in result:
                result[key] += 1

        return Response(result, status=200)
