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
from workflow_manager.serializers.analysis import AnalysisListQueryParamSerializer
from workflow_manager.serializers.analysis_run import AnalysisRunListQueryParamSerializer
from workflow_manager.serializers.stats import (
    WorkflowRunStatusCountSerializer,
    AnalysisRunStatusCountSerializer,
    WorkflowStatusCountSerializer,
    AnalysisStatusCountSerializer,
)
from workflow_manager.serializers.workflow import WorkflowListQueryParamSerializer
from workflow_manager.serializers.workflow_run import WorkflowRunListQueryParamSerializer
from workflow_manager.viewsets.utils import (
    WORKFLOW_RUN_TERMINATION_STATUSES,
    get_latest_workflow_ids_queryset,
    filtered_workflow_runs_queryset,
    filtered_analysis_runs_queryset,
    filtered_analyses_queryset,
    filtered_workflows_queryset,
)

RUN_LATEST_STATE_TERMINATION_STATUSES = WORKFLOW_RUN_TERMINATION_STATUSES


def _run_latest_state_bucket_counts(
    parent_model,
    state_model,
    *,
    state_fk_field: str,
    termination_statuses,
    base_queryset=None,
):
    """Count parent rows (e.g. WorkflowRun) by latest linked state row status (one row per parent).

    Tie-break on equal ``timestamp`` uses ``-orcabus_id`` so each parent contributes to exactly one bucket.
    """
    latest_status_sq = (
        state_model.objects.filter(**{state_fk_field: OuterRef("pk")})
        .order_by("-timestamp", "-orcabus_id")
        .values("status")[:1]
    )
    parent_qs = base_queryset if base_queryset is not None else parent_model.objects.all()
    qs = parent_qs.annotate(latest_status=Subquery(latest_status_sq))
    grouped_counts = {
        row["latest_status"]: row["count"]
        for row in qs.values("latest_status").annotate(count=Count("pk", distinct=True))
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

    # --- workflow run ---

    def _workflow_run_status_counts(self, query_params):
        base = filtered_workflow_runs_queryset(
            query_params,
            termination_statuses=RUN_LATEST_STATE_TERMINATION_STATUSES,
            apply_status_filter=False,
        )
        return _run_latest_state_bucket_counts(
            WorkflowRun,
            State,
            state_fk_field="workflow_run",
            termination_statuses=RUN_LATEST_STATE_TERMINATION_STATUSES,
            base_queryset=base,
        )

    @extend_schema(
        parameters=[WorkflowRunListQueryParamSerializer],
        responses=WorkflowRunStatusCountSerializer,
        description=(
            "Counts of workflow runs grouped by latest state status. "
            "Accepts the same query parameters as the workflow run list (keyword filters, search, "
            "start_time/end_time on latest state time, is_ongoing) except status and ordering."
        ),
    )
    @action(detail=False, methods=["GET"], url_path="workflow_run/status_counts")
    def workflow_run_status_counts(self, request):
        return Response(self._workflow_run_status_counts(request.query_params), status=200)

    # --- analysis run ---

    def _analysis_run_status_counts(self, query_params):
        base = filtered_analysis_runs_queryset(
            query_params,
            termination_statuses=RUN_LATEST_STATE_TERMINATION_STATUSES,
            apply_status_filter=False,
        )
        return _run_latest_state_bucket_counts(
            AnalysisRun,
            AnalysisRunState,
            state_fk_field="analysis_run",
            termination_statuses=RUN_LATEST_STATE_TERMINATION_STATUSES,
            base_queryset=base,
        )

    @extend_schema(
        parameters=[AnalysisRunListQueryParamSerializer],
        responses=AnalysisRunStatusCountSerializer,
        description=(
            "Counts of analysis runs grouped by latest state status. "
            "Accepts keyword filters, search, start_time/end_time except status and ordering."
        ),
    )
    @action(detail=False, methods=["GET"], url_path="analysis_run/status_counts")
    def analysis_run_status_counts(self, request):
        return Response(self._analysis_run_status_counts(request.query_params), status=200)

    # --- workflow ---

    @extend_schema(
        parameters=[WorkflowListQueryParamSerializer],
        responses=WorkflowStatusCountSerializer,
        description=(
            "Counts of workflow definitions grouped by validation state. "
            "Accepts keyword filters and search except status and ordering."
        ),
    )
    @action(detail=False, methods=["GET"], url_path="workflow/status_counts")
    def workflow_status_counts(self, request):
        base = filtered_workflows_queryset(
            request.query_params,
            apply_status_filter=False,
        )
        counts = (
            base.values("validation_state")
            .annotate(count=Count("orcabus_id", distinct=True))
            .order_by("validation_state")
        )
        result = {
            "all": base.count(),
            **{vs.value.lower(): 0 for vs in ValidationState},
        }
        for row in counts:
            key = row["validation_state"].lower()
            result[key] = row["count"]

        return Response(result, status=200)

    # --- analysis ---

    @extend_schema(
        parameters=[AnalysisListQueryParamSerializer],
        responses=AnalysisStatusCountSerializer,
        description=(
            "Counts of analysis definitions grouped by status. "
            "Accepts keyword filters and search except status and ordering."
        ),
    )
    @action(detail=False, methods=["GET"], url_path="analysis/status_counts")
    def analysis_status_counts(self, request):
        base = filtered_analyses_queryset(
            request.query_params,
            apply_status_filter=False,
        )
        counts = (
            base.values("status")
            .annotate(count=Count("orcabus_id", distinct=True))
            .order_by("status")
        )
        result = {
            "all": base.count(),
            **{s.value.lower(): 0 for s in AnalysisStatus},
        }
        for row in counts:
            key = row["status"].lower()
            result[key] = row["count"]

        return Response(result, status=200)

    # --- grouped workflow ---

    @extend_schema(
        parameters=[WorkflowListQueryParamSerializer],
        responses=WorkflowStatusCountSerializer,
        description=(
            "Counts of grouped workflows by validation state. "
            "Workflows are grouped by name and only the latest version per group is counted. "
            "Accepts keyword filters, search, and status (applied to the latest workflows only). "
            "Ordering is ignored."
        ),
    )
    @action(detail=False, methods=["GET"], url_path="grouped_workflow/status_counts")
    def grouped_workflow_status_counts(self, request):
        # Decide "latest version per name group" in the DB before applying user
        # filters.  This avoids materialising all Workflow rows in Python and
        # generating a large IN (...) clause.
        latest_ids_qs = get_latest_workflow_ids_queryset()

        filtered_latest_qs = (
            filtered_workflows_queryset(request.query_params)
            .filter(orcabus_id__in=latest_ids_qs)
        )

        counts = (
            filtered_latest_qs.values("validation_state")
            .annotate(count=Count("orcabus_id", distinct=True))
            .order_by("validation_state")
        )

        result = {
            "all": filtered_latest_qs.count(),
            **{vs.value.lower(): 0 for vs in ValidationState},
        }
        for row in counts:
            key = row["validation_state"].lower()
            if key in result:
                result[key] = row["count"]

        return Response(result, status=200)
