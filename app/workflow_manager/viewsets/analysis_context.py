from drf_spectacular.utils import extend_schema

from workflow_manager.models.analysis_context import AnalysisContext
from workflow_manager.serializers.analysis_context import AnalysisContextSerializer, AnalysisContextListParamSerializer, \
    UpdatableAnalysisContextSerializer
from .base import PatchOnlyViewSet


class AnalysisContextViewSet(PatchOnlyViewSet):
    serializer_class = AnalysisContextSerializer
    search_fields = AnalysisContext.get_base_fields()

    def get_queryset(self):
        query_params = self.request.query_params.copy()
        return AnalysisContext.objects.get_by_keyword(self.queryset, **query_params)

    @extend_schema(parameters=[
        AnalysisContextListParamSerializer
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=UpdatableAnalysisContextSerializer,
    )
    def partial_update(self, request, *args, **kwargs):
        self.serializer_class = UpdatableAnalysisContextSerializer
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)
