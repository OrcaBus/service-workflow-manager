from datetime import datetime

from django.db.models import Q, Max, F, Value, Exists, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework import filters
from rest_framework.decorators import action

from workflow_manager.models.workflow_run import WorkflowRun
from workflow_manager.models.state import State
from workflow_manager.serializers.workflow_run import (
    WorkflowRunListQueryParamSerializer,
    WorkflowRunDetailSerializer,
    WorkflowRunSerializer,
)
from workflow_manager.viewsets.base import BaseViewSet

# Custom query params that this viewset handles (excluded from get_by_keyword)
CUSTOM_QUERY_PARAMS = frozenset([
    'start_time', 'end_time', 'is_ongoing', 'status', 'search', 'order_by'
])


def _build_keyword_params(query_params):
    """Build keyword params using getlist to preserve multiple values per key (e.g. workflow__orcabus_id=id1&workflow__orcabus_id=id2)."""
    return {
        k: query_params.getlist(k)
        for k in query_params
        if k not in CUSTOM_QUERY_PARAMS
        and query_params.getlist(k)
    }

# Allowed ordering fields for ongoing/unresolved actions (with optional - prefix)
ALLOWED_ORDER_FIELDS = frozenset([
    'orcabus_id', '-orcabus_id', 'portal_run_id', '-portal_run_id',
    'workflow_run_name', '-workflow_run_name', 'execution_id', '-execution_id',
    'comment', '-comment',
])


class WorkflowRunViewSet(BaseViewSet):
    """
    Read-only WorkflowRun API. Analysis_run linkage is updated automatically by the system.
    """
    serializer_class = WorkflowRunDetailSerializer
    search_fields = WorkflowRun.get_base_fields()
    queryset = WorkflowRun.objects.prefetch_related("libraries").all()
    termination_statuses = ["FAILED", "ABORTED", "SUCCEEDED", "RESOLVED", "DEPRECATED"]
    http_method_names = ['get', 'head', 'options', 'trace']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._has_custom_ordering = False

    @staticmethod
    def _validate_ordering(ordering: str, default: str = '-orcabus_id') -> str:
        """Validate ordering param against allowed fields; return default if invalid."""
        if not ordering or ordering.strip() not in ALLOWED_ORDER_FIELDS:
            return default
        return ordering.strip()

    @staticmethod
    def _parse_datetime_safe(value: str):
        """Parse datetime string; return None if invalid or empty."""
        if not value or not isinstance(value, str):
            return None
        return parse_datetime(value.strip())

    @extend_schema(
        parameters=[WorkflowRunListQueryParamSerializer],
        responses=WorkflowRunSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        self.serializer_class = WorkflowRunSerializer  # use simple view for record listing
        return super().list(request, *args, **kwargs)

    def filter_queryset(self, queryset):
        """
        Override to prevent OrderingFilter from applying default ordering
        when we have a custom order_by parameter.
        """
        # Check if we have custom ordering (stored in instance variable from get_queryset)
        if self._has_custom_ordering:
            # We have custom ordering, so we need to prevent OrderingFilter from applying default ordering
            # Temporarily store original filter_backends
            original_backends = self.filter_backends
            # Filter out OrderingFilter by checking the class type
            self.filter_backends = [f for f in self.filter_backends if f != filters.OrderingFilter]
            try:
                # Apply filters without OrderingFilter
                queryset = super().filter_queryset(queryset)
            finally:
                # Restore original filter_backends
                self.filter_backends = original_backends
        else:
            # No custom ordering, use default behavior
            queryset = super().filter_queryset(queryset)

        return queryset

    def get_queryset(self):
        """
        custom queryset:
        add filter by:
        start_time, end_time : range of latest state timestamp
        is_ongoing : filter by ongoing workflow runs
        status : filter by latest state status

        add search terms:
        library_id: filter by library_id
        orcabus_id: filter by orcabus_id

        add order_by:
        order_by: current state (latest state) timestamp
        (by default, order by first state timestamp)
        """
        start_time = self.request.query_params.get('start_time', '')
        end_time = self.request.query_params.get('end_time', '')
        start_dt = self._parse_datetime_safe(start_time) if start_time else None
        end_dt = self._parse_datetime_safe(end_time) if end_time else None

        is_ongoing = self.request.query_params.get('is_ongoing', 'false')
        status = self.request.query_params.get('status', '')
        search_params = self.request.query_params.get('search', '')
        order_by = self.request.query_params.get('order_by', '').strip()

        self._has_custom_ordering = bool(order_by)

        # Use filtered params with getlist to preserve multiple values (e.g. workflow__orcabus_id=id1,id2,id3)
        keyword_params = _build_keyword_params(self.request.query_params)

        result_set = (
            WorkflowRun.objects.get_by_keyword(**keyword_params)
            .distinct()
            .prefetch_related('states')
            .prefetch_related('libraries')
            .select_related('workflow', 'analysis_run')
        )

        needs_annotation = bool(start_dt and end_dt) or bool(status) or bool(order_by)

        # Add annotation once if needed, using Coalesce for ordering to handle NULL values
        if needs_annotation:
            if order_by:
                # Use Coalesce when ordering to handle NULL values (WorkflowRuns with no states)
                result_set = result_set.annotate(
                    latest_state_time=Coalesce(Max('states__timestamp'), Value(datetime.min))
                )
            else:
                # Simple annotation for filtering
                result_set = result_set.annotate(latest_state_time=Max('states__timestamp'))

        if start_dt and end_dt:
            result_set = result_set.filter(
                latest_state_time__range=[start_dt, end_dt]
            )

        if is_ongoing.lower() == 'true':
            result_set = result_set.filter(
                ~Q(states__status__in=self.termination_statuses)
            )

        if status:
            result_set = result_set.filter(
                states__timestamp=F('latest_state_time'),
                states__status=status.upper()
            )

        if order_by:
            if order_by == 'timestamp':
                # Ascending order: oldest first
                result_set = result_set.order_by('latest_state_time', '-orcabus_id')
            elif order_by == '-timestamp':
                # Descending order: newest first
                result_set = result_set.order_by('-latest_state_time', '-orcabus_id')

        # Combine search across multiple fields (workflow run name, comment, library_id, orcabus_id, workflow name)
        if search_params:
            result_set = result_set.filter(
                Q(workflow_run_name__icontains=search_params) |
                Q(comment__icontains=search_params) |
                Q(libraries__library_id__icontains=search_params) |
                Q(libraries__orcabus_id__icontains=search_params) |
                Q(workflow__name__icontains=search_params)
            ).distinct() # Add distinct to remove duplicates

        return result_set

    @extend_schema(
        responses=WorkflowRunSerializer(many=True),
        summary="List ongoing workflow runs",
        description="Returns workflow runs whose latest state is not in a terminal status (FAILED, ABORTED, SUCCEEDED, RESOLVED, DEPRECATED).",
    )
    @action(detail=False, methods=['GET'])
    def ongoing(self, request):
        self.serializer_class = WorkflowRunSerializer
        ordering = self._validate_ordering(
            request.query_params.get('ordering', ''),
            default='-orcabus_id'
        )

        keyword_params = _build_keyword_params(request.query_params)
        if "status" in request.query_params:
            keyword_params['states__status'] = request.query_params.get('status')

        # Exclude runs where the latest state (by timestamp) is in a terminal status.
        # Annotate with latest timestamp, then exclude where that state is terminal.
        # Using annotate+OuterRef avoids nested Subquery/OuterRef correlation issues.
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

        result_set = (
            WorkflowRun.objects.get_by_keyword(**keyword_params)
            .annotate(latest_state_time=Subquery(latest_ts_subq))
            .exclude(has_terminal_latest)
            .order_by(ordering)
            .prefetch_related('states', 'libraries')
            .select_related('workflow', 'analysis_run')
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
        ordering = self._validate_ordering(
            request.query_params.get('ordering', ''),
            default='-orcabus_id'
        )

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

        result_set = (
            WorkflowRun.objects.annotate(latest_state_time=Subquery(latest_ts_subq))
            .filter(has_failed_latest)
            .order_by(ordering)
            .prefetch_related('states', 'libraries')
            .select_related('workflow', 'analysis_run')
        )
        page_qs = self.paginate_queryset(result_set)
        serializer = self.get_serializer(page_qs, many=True)
        return self.get_paginated_response(serializer.data)
