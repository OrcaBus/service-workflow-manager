from drf_spectacular.utils import extend_schema
from rest_framework import status

from workflow_manager.models.analysis import Analysis
from workflow_manager.serializers.analysis import AnalysisSerializer, AnalysisListParamSerializer, \
    UpdatableAnalysisSerializer
from .base import PatchOnlyViewSet


class AnalysisViewSet(PatchOnlyViewSet):
    serializer_class = AnalysisSerializer
    search_fields = Analysis.get_base_fields()
    queryset = Analysis.objects.prefetch_related("contexts").prefetch_related("workflows").all()

    def get_queryset(self):
        query_params = self.request.query_params.copy()
        return Analysis.objects.get_by_keyword(self.queryset, **query_params)

    @extend_schema(parameters=[
        AnalysisListParamSerializer
    ])
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
