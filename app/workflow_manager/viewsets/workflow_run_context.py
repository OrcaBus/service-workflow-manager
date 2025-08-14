from drf_spectacular.utils import extend_schema
from rest_framework import status

from workflow_manager.models.workflow_run_context import WorkflowRunContext
from workflow_manager.serializers.workflow_run_context import WorkflowRunContextListParamSerializer, \
    WorkflowRunContextSerializer, UpdatableWorkflowRunContextSerializer
from workflow_manager.viewsets.base import PatchOnlyViewSet


class WorkflowRunContextViewSet(PatchOnlyViewSet):
    serializer_class = WorkflowRunContextSerializer
    search_fields = WorkflowRunContext.get_base_fields()

    def get_queryset(self):
        query_params = self.request.query_params.copy()
        return WorkflowRunContext.objects.get_by_keyword(self.queryset, **query_params)

    @extend_schema(parameters=[
        WorkflowRunContextListParamSerializer
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=UpdatableWorkflowRunContextSerializer,
        responses={
            status.HTTP_200_OK: UpdatableWorkflowRunContextSerializer,
        }
    )
    def partial_update(self, request, *args, **kwargs):
        self.serializer_class = UpdatableWorkflowRunContextSerializer
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)
