from drf_spectacular.utils import extend_schema
from rest_framework import status

from workflow_manager.models.analysis_run_context import AnalysisRunContext
from workflow_manager.serializers.analysis_run_context import AnalysisRunContextSerializer, \
    AnalysisRunContextListParamSerializer, UpdatableAnalysisRunContextSerializer
from workflow_manager.viewsets.base import PatchOnlyViewSet


class AnalysisRunContextViewSet(PatchOnlyViewSet):
    serializer_class = AnalysisRunContextSerializer
    search_fields = AnalysisRunContext.get_base_fields()

    def get_queryset(self):
        query_params = self.request.query_params.copy()
        return AnalysisRunContext.objects.get_by_keyword(self.queryset, **query_params)

    @extend_schema(parameters=[
        AnalysisRunContextListParamSerializer
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=UpdatableAnalysisRunContextSerializer,
        responses={
            status.HTTP_200_OK: UpdatableAnalysisRunContextSerializer,
        }
    )
    def partial_update(self, request, *args, **kwargs):
        self.serializer_class = UpdatableAnalysisRunContextSerializer
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)
