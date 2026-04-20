from drf_spectacular.utils import extend_schema
from rest_framework.settings import api_settings

from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager.serializers.analysis_run import (
    AnalysisRunDetailSerializer,
    AnalysisRunSerializer,
    AnalysisRunListQueryParamSerializer,
)
from workflow_manager.viewsets.base import BaseViewSet
from workflow_manager.viewsets.utils import (
    filtered_analysis_runs_queryset,
    validate_ordering,
)

ALLOWED_ORDER_FIELDS = frozenset([
    'orcabus_id', '-orcabus_id',
    'analysis_run_name', '-analysis_run_name',
    'comment', '-comment',
    'timestamp', '-timestamp',
])


class AnalysisRunViewSet(BaseViewSet):
    """
    Read-only AnalysisRun API. Create and update are handled automatically by the system (e.g. via events).
    """
    serializer_class = AnalysisRunDetailSerializer
    search_fields = AnalysisRun.get_base_fields()
    queryset = AnalysisRun.objects.prefetch_related(
        "libraries", "contexts", "readsets", "states"
    ).select_related("analysis").all()
    filter_backends = []

    def get_serializer_class(self):
        if self.action == "list":
            return AnalysisRunSerializer
        return AnalysisRunDetailSerializer

    @extend_schema(parameters=[AnalysisRunListQueryParamSerializer])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        raw_order = (self.request.query_params.get(api_settings.ORDERING_PARAM) or "").strip()
        validated = validate_ordering(raw_order, ALLOWED_ORDER_FIELDS)
        needs_timestamp_order = validated in ("timestamp", "-timestamp")

        result_set = filtered_analysis_runs_queryset(
            self.request.query_params,
            apply_status_filter=True,
            annotate_latest_state_time=needs_timestamp_order,
        )

        if needs_timestamp_order:
            if validated == "timestamp":
                return result_set.order_by("latest_state_time", "-orcabus_id")
            return result_set.order_by("-latest_state_time", "-orcabus_id")

        ordering = validated if validated else self.ordering[0]
        return result_set.order_by(ordering)
