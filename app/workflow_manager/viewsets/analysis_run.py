from drf_spectacular.utils import extend_schema

from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager.serializers.analysis_run import (
    AnalysisRunDetailSerializer,
    AnalysisRunSerializer,
    AnalysisRunListParamSerializer,
)
from .base import BaseViewSet


class AnalysisRunViewSet(BaseViewSet):
    """
    Read-only AnalysisRun API. Create and update are handled automatically by the system (e.g. via events).
    """
    serializer_class = AnalysisRunDetailSerializer  # use detailed for retrieve
    search_fields = AnalysisRun.get_base_fields()
    queryset = AnalysisRun.objects.prefetch_related(
        "libraries", "contexts", "readsets", "states"
    ).select_related("analysis").all()

    def get_serializer_class(self):
        if self.action == "list":
            return AnalysisRunSerializer
        return AnalysisRunDetailSerializer

    @extend_schema(parameters=[
        AnalysisRunListParamSerializer,
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        query_params = self.request.query_params.copy()
        return AnalysisRun.objects.get_by_keyword(self.queryset, **query_params)
