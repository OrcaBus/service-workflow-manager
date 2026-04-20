from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.settings import api_settings

from workflow_manager.models.analysis import Analysis
from workflow_manager.serializers.analysis import (
    AnalysisSerializer,
    AnalysisListQueryParamSerializer,
    UpdatableAnalysisSerializer,
)
from workflow_manager.viewsets.base import PatchOnlyViewSet
from workflow_manager.viewsets.utils import filtered_analyses_queryset, validate_ordering

ALLOWED_ORDER_FIELDS = frozenset([
    'orcabus_id', '-orcabus_id',
    'analysis_name', '-analysis_name',
    'analysis_version', '-analysis_version',
    'status', '-status',
    'description', '-description',
])


class AnalysisViewSet(PatchOnlyViewSet):
    serializer_class = AnalysisSerializer
    search_fields = Analysis.get_base_fields()
    queryset = Analysis.objects.prefetch_related("contexts").prefetch_related("workflows").all()
    filter_backends = []

    def get_queryset(self):
        result_set = filtered_analyses_queryset(self.request.query_params)

        raw_order = (self.request.query_params.get(api_settings.ORDERING_PARAM) or "").strip()
        validated = validate_ordering(raw_order, ALLOWED_ORDER_FIELDS)
        ordering = validated if validated else self.ordering[0]
        return result_set.order_by(ordering)

    @extend_schema(parameters=[AnalysisListQueryParamSerializer])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=UpdatableAnalysisSerializer,
        responses={
            status.HTTP_200_OK: UpdatableAnalysisSerializer,
        }
    )
    def partial_update(self, request, *args, **kwargs):
        self.serializer_class = UpdatableAnalysisSerializer
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)
