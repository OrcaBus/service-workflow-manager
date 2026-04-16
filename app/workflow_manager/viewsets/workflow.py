from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.settings import api_settings

from workflow_manager.models.workflow import Workflow
from workflow_manager.serializers.workflow import (
    WorkflowSerializer,
    WorkflowListQueryParamSerializer,
    WorkflowListSerializer,
)
from workflow_manager.viewsets.base import PostOnlyViewSet
from workflow_manager.viewsets.utils import (
    get_latest_workflows_by_name_group,
    filtered_workflows_queryset,
    validate_ordering,
)

ALLOWED_ORDER_FIELDS = frozenset([
    'orcabus_id', '-orcabus_id',
    'name', '-name',
    'version', '-version',
    'code_version', '-code_version',
    'execution_engine', '-execution_engine',
    'validation_state', '-validation_state',
])


class WorkflowViewSet(PostOnlyViewSet):
    serializer_class = WorkflowSerializer
    search_fields = Workflow.get_base_fields()
    filter_backends = []

    def get_queryset(self):
        result_set = filtered_workflows_queryset(self.request.query_params)

        raw_order = (self.request.query_params.get(api_settings.ORDERING_PARAM) or "").strip()
        validated = validate_ordering(raw_order, ALLOWED_ORDER_FIELDS)
        ordering = validated if validated else self.ordering[0]
        return result_set.order_by(ordering)

    @extend_schema(
        parameters=[WorkflowListQueryParamSerializer],
        responses=WorkflowSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[WorkflowListQueryParamSerializer],
        responses=WorkflowListSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="grouped")
    def grouped(self, request, *args, **kwargs):
        """List workflows grouped by name, returning the latest version with full version history."""
        # Group first so the "latest per name" decision is based on the full version set.
        # Only after selecting the latest versions do we apply filters (status/search/etc).
        all_latest_list, history_map_all = get_latest_workflows_by_name_group(
            Workflow.objects.all()
        )
        latest_ids = [w.orcabus_id for w in all_latest_list]

        filtered_latest_qs = (
            filtered_workflows_queryset(request.query_params)
            .filter(orcabus_id__in=latest_ids)
        )

        raw_order = (request.query_params.get(api_settings.ORDERING_PARAM) or "").strip()
        validated = validate_ordering(raw_order, ALLOWED_ORDER_FIELDS)
        ordering = validated if validated else self.ordering[0]
        filtered_latest_qs = filtered_latest_qs.order_by(ordering)

        page = self.paginate_queryset(filtered_latest_qs)
        page_history_map = {
            w.orcabus_id: history_map_all[w.orcabus_id]
            for w in page
            if w.orcabus_id in history_map_all
        }

        serializer = WorkflowListSerializer(
            page, many=True, context={"history_map": page_history_map}
        )
        return self.get_paginated_response(serializer.data)
