from datetime import datetime

from django.db.models import Q, Max, F, Value
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from workflow_manager.models import WorkflowRun
from workflow_manager.serializers.workflow_run import (
    WorkflowRunCountByStatusSerializer,
    WorkflowRunDetailSerializer,
    WorkflowRunListQueryParamSerializer,
)
from workflow_manager.viewsets.workflow_run import _build_keyword_params


@extend_schema_view(
    list=extend_schema(
        parameters=[WorkflowRunListQueryParamSerializer],
        responses=WorkflowRunDetailSerializer(many=True),
    ),
)
class WorkflowRunStatsViewSet(mixins.ListModelMixin, GenericViewSet):
    serializer_class = WorkflowRunDetailSerializer
    pagination_class = None  # No pagination by default
    http_method_names = ['get']
    lookup_value_regex = "[^/]+"  # to allow id prefix
    termination_statuses = ["FAILED", "ABORTED", "SUCCEEDED", "RESOLVED", "DEPRECATED"]

    @staticmethod
    def _parse_datetime_safe(value: str):
        """Parse datetime string; return None if invalid or empty."""
        if not value or not isinstance(value, str):
            return None
        return parse_datetime(value.strip())

    def get_queryset(self):
        """
        Same filtering semantics as WorkflowRunViewSet.list (time range, is_ongoing, status,
        search, order_by, and get_by_keyword field filters).
        """
        start_time = self.request.query_params.get('start_time', '')
        end_time = self.request.query_params.get('end_time', '')
        start_dt = self._parse_datetime_safe(start_time) if start_time else None
        end_dt = self._parse_datetime_safe(end_time) if end_time else None

        is_ongoing = self.request.query_params.get('is_ongoing', 'false')
        status = self.request.query_params.get('status', '')
        search_params = self.request.query_params.get('search', '')
        order_by = self.request.query_params.get('order_by', '').strip()

        keyword_params = _build_keyword_params(self.request.query_params)

        result_set = (
            WorkflowRun.objects.get_by_keyword(**keyword_params)
            .distinct()
            .prefetch_related('states')
            .prefetch_related('libraries')
            .select_related('workflow', 'analysis_run')
        )

        needs_annotation = bool(start_dt and end_dt) or bool(status) or bool(order_by)

        if needs_annotation:
            if order_by:
                result_set = result_set.annotate(
                    latest_state_time=Coalesce(Max('states__timestamp'), Value(datetime.min))
                )
            else:
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
                result_set = result_set.order_by('latest_state_time', '-orcabus_id')
            elif order_by == '-timestamp':
                result_set = result_set.order_by('-latest_state_time', '-orcabus_id')

        if search_params:
            result_set = result_set.filter(
                Q(workflow_run_name__icontains=search_params) |
                Q(comment__icontains=search_params) |
                Q(libraries__library_id__icontains=search_params) |
                Q(libraries__orcabus_id__icontains=search_params) |
                Q(workflow__name__icontains=search_params)
            ).distinct()

        return result_set

    @extend_schema(
        parameters=[WorkflowRunListQueryParamSerializer],
        responses=WorkflowRunDetailSerializer(many=True),
    )
    @action(detail=False, methods=['GET'], url_path='list_all')
    def list_all(self, request):
        return self.list(request)

    @extend_schema(
        parameters=[WorkflowRunListQueryParamSerializer],
        responses=WorkflowRunCountByStatusSerializer,
        description=(
            "Returns counts for each bucket: all, succeeded, aborted, failed, resolved, "
            "deprecated, and ongoing (latest state not terminal), using the same filters as "
            "the workflow run list."
        ),
    )
    @action(detail=False, methods=['GET'])
    def count_by_status(self, request):
        base_queryset = self.get_queryset()

        all_count = base_queryset.count()

        annotate_queryset = base_queryset.annotate(latest_state_time=Max('states__timestamp'))

        succeeded_count = annotate_queryset.filter(
            states__timestamp=F('latest_state_time'),
            states__status="SUCCEEDED"
        ).count()

        aborted_count = annotate_queryset.filter(
            states__timestamp=F('latest_state_time'),
            states__status="ABORTED"
        ).count()

        failed_count = annotate_queryset.filter(
            states__timestamp=F('latest_state_time'),
            states__status="FAILED"
        ).count()

        resolved_count = annotate_queryset.filter(
            states__timestamp=F('latest_state_time'),
            states__status="RESOLVED"
        ).count()

        deprecated_count = annotate_queryset.filter(
            states__timestamp=F('latest_state_time'),
            states__status="DEPRECATED"
        ).count()

        ongoing_count = annotate_queryset.filter(
            Q(states__timestamp=F('latest_state_time')) &
            ~Q(states__status__in=self.termination_statuses)
        ).count()

        return Response({
            'all': all_count,
            'succeeded': succeeded_count,
            'aborted': aborted_count,
            'failed': failed_count,
            'resolved': resolved_count,
            'deprecated': deprecated_count,
            'ongoing': ongoing_count
        }, status=200)
