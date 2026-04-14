from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

from workflow_manager.models.workflow import Workflow
from workflow_manager.serializers.workflow import (
    WorkflowSerializer,
    WorkflowListParamSerializer,
    WorkflowListSerializer,
)
from workflow_manager.viewsets.base import PostOnlyViewSet
from workflow_manager.viewsets.workflow_utils import get_latest_workflows_by_name_group


class WorkflowViewSet(PostOnlyViewSet):
    serializer_class = WorkflowSerializer
    search_fields = Workflow.get_base_fields()

    def get_queryset(self):
        query_params = self.request.query_params.copy()
        return Workflow.objects.get_by_keyword(self.queryset, **query_params)

    @extend_schema(
        parameters=[WorkflowListParamSerializer],
        responses=WorkflowSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[WorkflowListParamSerializer],
        responses=WorkflowListSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="grouped")
    def grouped(self, request, *args, **kwargs):
        """List workflows grouped by name, returning the latest version with full version history."""
        queryset = self.filter_queryset(self.get_queryset())
        latest_list, history_map = get_latest_workflows_by_name_group(queryset)
        page = self.paginate_queryset(latest_list)
        serializer = WorkflowListSerializer(
            page, many=True, context={"history_map": history_map}
        )
        return self.get_paginated_response(serializer.data)
