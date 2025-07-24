from drf_spectacular.utils import extend_schema
from rest_framework import status

from workflow_manager.models.workflow import Workflow
from workflow_manager.serializers.workflow import WorkflowSerializer, WorkflowListParamSerializer, \
    UpdatableWorkflowSerializer
from workflow_manager.viewsets.base import PatchOnlyViewSet


class WorkflowViewSet(PatchOnlyViewSet):
    serializer_class = WorkflowSerializer
    search_fields = Workflow.get_base_fields()

    def get_queryset(self):
        query_params = self.request.query_params.copy()
        return Workflow.objects.get_by_keyword(self.queryset, **query_params)

    @extend_schema(parameters=[
        WorkflowListParamSerializer
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=UpdatableWorkflowSerializer,
        responses={
            status.HTTP_200_OK: UpdatableWorkflowSerializer,
        }
    )
    def partial_update(self, request, *args, **kwargs):
        self.serializer_class = UpdatableWorkflowSerializer
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)
