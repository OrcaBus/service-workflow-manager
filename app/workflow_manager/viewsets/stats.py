from django.db.models import Count, OuterRef, Subquery
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from workflow_manager.models import WorkflowRun
from workflow_manager.models.analysis_run_state import AnalysisRunState
from workflow_manager.models.state import State
from workflow_manager.models.analysis import Analysis, AnalysisStatus
from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager.models.workflow import Workflow, ValidationState
from workflow_manager.serializers.stats import (
    WorkflowRunStatusCountSerializer,
    AnalysisRunStatusCountSerializer,
    WorkflowStatusCountSerializer,
    AnalysisStatusCountSerializer,
)
from workflow_manager.viewsets.workflow_utils import get_latest_workflows_by_name_group

# Latest-state "terminal" buckets for workflow runs and analysis runs (ongoing = not in this set).
RUN_LATEST_STATE_TERMINATION_STATUSES = (
    "FAILED",
    "ABORTED",
    "SUCCEEDED",
    "RESOLVED",
    "DEPRECATED",
)


def _run_latest_state_bucket_counts(parent_model, state_model, *, state_fk_field: str, termination_statuses):
    """Count parent rows (e.g. WorkflowRun) by latest linked state row status (one row per parent).

    Tie-break on equal ``timestamp`` uses ``-orcabus_id`` so each parent contributes to exactly one bucket.
    """
    latest_status_sq = (
        state_model.objects.filter(**{state_fk_field: OuterRef("pk")})
        .order_by("-timestamp", "-orcabus_id")
        .values("status")[:1]
    )
    qs = parent_model.objects.annotate(latest_status=Subquery(latest_status_sq))
    grouped_counts = {
        row["latest_status"]: row["count"]
        for row in qs.values("latest_status").annotate(count=Count("pk"))
    }
    all_count = sum(grouped_counts.values())
    succeeded = grouped_counts.get("SUCCEEDED", 0)
    aborted = grouped_counts.get("ABORTED", 0)
    failed = grouped_counts.get("FAILED", 0)
    resolved = grouped_counts.get("RESOLVED", 0)
    deprecated = grouped_counts.get("DEPRECATED", 0)
    ongoing = sum(
        count
        for status, count in grouped_counts.items()
        if status is not None and status not in termination_statuses
    )

    return {
        "all": all_count,
        "succeeded": succeeded,
        "aborted": aborted,
        "failed": failed,
        "resolved": resolved,
        "deprecated": deprecated,
        "ongoing": ongoing,
    }


class StatsViewSet(GenericViewSet):
    """Read-only aggregate statistics for workflow runs, analysis runs, workflows, and analyses."""

    pagination_class = None
    http_method_names = ["get"]

    def _workflow_run_status_counts(self):
        """Count WorkflowRun records grouped by their latest State status."""
        return _run_latest_state_bucket_counts(
            WorkflowRun,
            State,
            state_fk_field="workflow_run",
            termination_statuses=RUN_LATEST_STATE_TERMINATION_STATUSES,
        )

    def _analysis_run_status_counts(self):
        """Count AnalysisRun records grouped by their latest AnalysisRunState status."""
        return _run_latest_state_bucket_counts(
            AnalysisRun,
            AnalysisRunState,
            state_fk_field="analysis_run",
            termination_statuses=RUN_LATEST_STATE_TERMINATION_STATUSES,
        )

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

    @extend_schema(
        responses=WorkflowStatusCountSerializer,
        description=(
            "Counts of grouped workflows by validation state. "
            "Workflows are grouped by name and only the latest version per group is counted."
        ),
    )
    @action(detail=False, methods=["GET"], url_path="grouped_workflow/status_counts")
    def grouped_workflow_status_counts(self, request):
        latest_workflows, _ = get_latest_workflows_by_name_group(Workflow.objects.all())

        result = {
            "all": len(latest_workflows),
            **{vs.value.lower(): 0 for vs in ValidationState},
        }
        for w in latest_workflows:
            key = w.validation_state.lower()
            if key in result:
                result[key] += 1

        return Response(result, status=200)
