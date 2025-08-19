from drf_spectacular.utils import extend_schema
from rest_framework import status

from workflow_manager.models.run_context import RunContext
from workflow_manager.serializers.run_context import RunContextSerializer, RunContextListParamSerializer, \
    UpdatableRunContextSerializer
from workflow_manager.viewsets.base import PatchOnlyViewSet


class RunContextViewSet(PatchOnlyViewSet):
    serializer_class = RunContextSerializer
    search_fields = RunContext.get_base_fields()

    def get_queryset(self):
        query_params = self.request.query_params.copy()
        return RunContext.objects.get_by_keyword(self.queryset, **query_params)

    @extend_schema(parameters=[
        RunContextListParamSerializer
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=UpdatableRunContextSerializer,
        responses={
            status.HTTP_200_OK: UpdatableRunContextSerializer,
        }
    )
    def partial_update(self, request, *args, **kwargs):
        self.serializer_class = UpdatableRunContextSerializer
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)
