from django.db.models import Q, Exists, OuterRef, Subquery
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.settings import api_settings

from workflow_manager.models.workflow_run import WorkflowRun
from workflow_manager.models.state import State
from workflow_manager.serializers.workflow_run import (
    WorkflowRunListQueryParamSerializer,
    WorkflowRunDetailSerializer,
    WorkflowRunSerializer,
)
from workflow_manager.viewsets.base import BaseViewSet
from workflow_manager.viewsets.utils import filtered_workflow_runs_queryset, validate_ordering

ALLOWED_ORDER_FIELDS = frozenset([
    'orcabus_id', '-orcabus_id', 'portal_run_id', '-portal_run_id',
    'workflow_run_name', '-workflow_run_name', 'execution_id', '-execution_id',
    'comment', '-comment',
    'timestamp', '-timestamp',
])


class WorkflowRunViewSet(BaseViewSet):
    """
    Read-only WorkflowRun API. Analysis_run linkage is updated automatically by the system.
    """
    serializer_class = WorkflowRunDetailSerializer
    search_fields = WorkflowRun.get_base_fields()
    queryset = WorkflowRun.objects.all()
    termination_statuses = ["FAILED", "ABORTED", "SUCCEEDED", "RESOLVED", "DEPRECATED"]
    http_method_names = ['get', 'head', 'options', 'trace']
    # Ordering and search are handled in get_queryset / filtered_workflow_runs_queryset;
    # DRF filter_backends are disabled to avoid double-filtering.
    filter_backends = []

    @extend_schema(
        parameters=[WorkflowRunListQueryParamSerializer],
        responses=WorkflowRunSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        self.serializer_class = WorkflowRunSerializer
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        """
        Same shared filters as stats (see ``filtered_workflow_runs_queryset``).
        The ``status`` query param filters by the **latest** state status on each run.
        Optional ``ordering`` (``REST_FRAMEWORK['ORDERING_PARAM']``) when the value is
        in the allow-list; falls back to ``-orcabus_id`` when absent or invalid.
        ``timestamp`` / ``-timestamp`` sort by latest state time.
        """
        raw_order = (self.request.query_params.get(api_settings.ORDERING_PARAM) or "").strip()
        validated = validate_ordering(raw_order, ALLOWED_ORDER_FIELDS)
        needs_timestamp_order = validated in ("timestamp", "-timestamp")

        result_set = filtered_workflow_runs_queryset(
            self.request.query_params,
            termination_statuses=self.termination_statuses,
            apply_status_filter=True,
            annotate_latest_state_time=needs_timestamp_order,
        )

        if self.action == "retrieve":
            result_set = result_set.prefetch_related("contexts", "readsets")

        if needs_timestamp_order:
            if validated == "timestamp":
                return result_set.order_by("latest_state_time", "-orcabus_id")
            return result_set.order_by("-latest_state_time", "-orcabus_id")

        ordering = validated if validated else self.ordering[0]
        return result_set.order_by(ordering)

    @extend_schema(
        responses=WorkflowRunSerializer(many=True),
        summary="List ongoing workflow runs",
        description="Returns workflow runs whose latest state is not in a terminal status (FAILED, ABORTED, SUCCEEDED, RESOLVED, DEPRECATED).",
    )
    @action(detail=False, methods=['GET'])
    def ongoing(self, request):
        self.serializer_class = WorkflowRunSerializer
        validated = validate_ordering(
            request.query_params.get(api_settings.ORDERING_PARAM, ''),
            ALLOWED_ORDER_FIELDS,
        )
        ordering = validated if validated else '-orcabus_id'

        extra_keyword: dict[str, list[str]] = {}
        if "status" in request.query_params:
            st = request.query_params.get("status")
            if st and str(st).strip():
                extra_keyword["states__status"] = [str(st).strip()]

        latest_ts_subq = State.objects.filter(
            workflow_run=OuterRef('pk'),
        ).order_by('-timestamp').values('timestamp')[:1]

        has_terminal_latest = Exists(
            State.objects.filter(
                workflow_run=OuterRef('pk'),
                timestamp=OuterRef('latest_state_time'),
                status__in=self.termination_statuses,
            )
        )

        base = filtered_workflow_runs_queryset(
            request.query_params,
            extra_keyword_params=extra_keyword or None,
        )
        result_set = (
            base.annotate(latest_state_time=Subquery(latest_ts_subq))
            .exclude(has_terminal_latest)
            .order_by(ordering)
        )
        page_qs = self.paginate_queryset(result_set)
        serializer = self.get_serializer(page_qs, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        responses=WorkflowRunSerializer(many=True),
        summary="List unresolved workflow runs",
        description="Returns workflow runs whose latest state is FAILED (failed runs not yet resolved).",
    )
    @action(detail=False, methods=['GET'])
    def unresolved(self, request):
        self.serializer_class = WorkflowRunSerializer
        validated = validate_ordering(
            request.query_params.get(api_settings.ORDERING_PARAM, ''),
            ALLOWED_ORDER_FIELDS,
        )
        ordering = validated if validated else '-orcabus_id'

        latest_ts_subq = State.objects.filter(
            workflow_run=OuterRef('pk'),
        ).order_by('-timestamp').values('timestamp')[:1]

        has_failed_latest = Exists(
            State.objects.filter(
                workflow_run=OuterRef('pk'),
                timestamp=OuterRef('latest_state_time'),
                status='FAILED',
            )
        )

        base = filtered_workflow_runs_queryset(request.query_params)
        result_set = (
            base.annotate(latest_state_time=Subquery(latest_ts_subq))
            .filter(has_failed_latest)
            .order_by(ordering)
        )
        page_qs = self.paginate_queryset(result_set)
        serializer = self.get_serializer(page_qs, many=True)
        return self.get_paginated_response(serializer.data)
