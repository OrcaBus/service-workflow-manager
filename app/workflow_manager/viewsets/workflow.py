from collections import defaultdict

from drf_spectacular.utils import extend_schema

from workflow_manager.models.workflow import Workflow
from workflow_manager.serializers.workflow import (
    WorkflowSerializer,
    WorkflowListParamSerializer,
    WorkflowListSerializer,
)
from workflow_manager.serializers.base import version_sort_key
from workflow_manager.viewsets.base import PostOnlyViewSet


class WorkflowViewSet(PostOnlyViewSet):
    serializer_class = WorkflowSerializer
    search_fields = Workflow.get_base_fields()

    def get_queryset(self):
        query_params = self.request.query_params.copy()
        return Workflow.objects.get_by_keyword(self.queryset, **query_params)

    def _get_latest_workflows_with_history(self, queryset):
        """
        Group workflows by name (case-insensitive), pick highest version per group
        (XX.XX.00 format), tie-break: first one. Return (latest_list, history_map).
        """
        all_workflows = list(queryset)
        grouped = defaultdict(list)
        for w in all_workflows:
            grouped[w.name.lower()].append(w)

        latest_list = []
        history_map = {}
        for name_key in sorted(grouped.keys()):
            group = grouped[name_key]
            # Sort by version desc; equal versions keep original order (stable sort)
            group.sort(key=lambda w: version_sort_key(w.version), reverse=True)
            latest = group[0]
            latest_list.append(latest)
            history_map[latest.orcabus_id] = group

        return latest_list, history_map

    @extend_schema(
        parameters=[WorkflowListParamSerializer],
        responses=WorkflowListSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        latest_list, history_map = self._get_latest_workflows_with_history(queryset)
        page = self.paginate_queryset(latest_list)
        serializer = WorkflowListSerializer(
            page, many=True, context={"history_map": history_map}
        )
        return self.get_paginated_response(serializer.data)
