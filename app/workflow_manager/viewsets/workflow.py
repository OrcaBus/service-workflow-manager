from collections import defaultdict

from django.db.models.functions import Lower
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
    get_latest_workflow_ids_queryset,
    filtered_workflows_queryset,
    validate_ordering,
    version_sort_key,
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
        # Decide "latest version per name group" in the DB using a window
        # function over semver components.  This avoids materialising all
        # Workflow rows in Python and building a large IN (...) clause.
        latest_ids_qs = get_latest_workflow_ids_queryset()

        filtered_latest_qs = (
            filtered_workflows_queryset(request.query_params)
            .filter(orcabus_id__in=latest_ids_qs)
        )

        raw_order = (request.query_params.get(api_settings.ORDERING_PARAM) or "").strip()
        validated = validate_ordering(raw_order, ALLOWED_ORDER_FIELDS)
        ordering = validated if validated else self.ordering[0]
        filtered_latest_qs = filtered_latest_qs.order_by(ordering)

        page = self.paginate_queryset(filtered_latest_qs)

        # Fetch version history only for the paginated page's name groups,
        # rather than loading all workflows upfront.
        page_names = {w.name.lower() for w in page}
        if page_names:
            history_rows = Workflow.objects.annotate(
                name_lower=Lower("name"),
            ).filter(name_lower__in=page_names)

            # Group by lowercase name, then map latest orcabus_id → group.
            name_groups: dict[str, list] = defaultdict(list)
            for w in history_rows:
                name_groups[w.name.lower()].append(w)
            for group in name_groups.values():
                group.sort(
                    key=lambda w: (version_sort_key(w.version), w.orcabus_id),
                    reverse=True,
                )

            page_history_map = {}
            for w in page:
                group = name_groups.get(w.name.lower(), [])
                page_history_map[w.orcabus_id] = group
        else:
            page_history_map = {}

        serializer = WorkflowListSerializer(
            page, many=True, context={"history_map": page_history_map}
        )
        return self.get_paginated_response(serializer.data)
