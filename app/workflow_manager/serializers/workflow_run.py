from rest_framework import serializers
from rest_framework.settings import api_settings

from workflow_manager.serializers.base import SerializersBase, OptionalFieldsMixin, OrcabusIdSerializerMetaMixin
from workflow_manager.models import WorkflowRun
from workflow_manager.serializers.state import StateMinSerializer


class WorkflowRunBaseSerializer(SerializersBase):
    # we only want to include the current state
    # all states are available via a dedicated endpoint
    current_state = serializers.SerializerMethodField()

    def get_current_state(self, obj) -> dict:
        latest_state = obj.get_latest_state()
        return StateMinSerializer(latest_state).data if latest_state else None


class WorkflowRunListParamSerializer(OptionalFieldsMixin, WorkflowRunBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = WorkflowRun
        fields = ["orcabus_id", "workflow", "analysis_run", "workflow_run_name", "portal_run_id", "execution_id",
                  "comment", ]


class WorkflowRunListQueryParamSerializer(WorkflowRunListParamSerializer):
    """
    Full query parameter schema for workflow run list and stats endpoints (OpenAPI / drf-spectacular).

    Includes model field filters from WorkflowRunListParamSerializer plus the custom filters
    implemented in WorkflowRunViewSet and ``StatsViewSet`` workflow run status counts.

    Free-text search and sort use the same query keys as DRF defaults
    (``REST_FRAMEWORK['SEARCH_PARAM']`` / ``['ORDERING_PARAM']``, typically ``search`` / ``ordering``).
    """

    start_time = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="ISO 8601 datetime; start of range on latest state timestamp.",
    )
    end_time = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="ISO 8601 datetime; end of range on latest state timestamp.",
    )
    is_ongoing = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text="If 'true', only runs whose latest state is not terminal.",
    )
    status = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Filter by latest state status (e.g. SUCCEEDED, FAILED).",
    )
    # Attribute names must match ``api_settings.SEARCH_PARAM`` / ``ORDERING_PARAM`` (defaults: search, ordering).
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=(
            "Substring search on workflow run name, comment, library ids, orcabus_id, "
            "portal_run_id, execution_id, and workflow name."
        ),
    )
    ordering = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=(
            "Sort order: model fields such as orcabus_id, -orcabus_id, portal_run_id; "
            "or latest state time via timestamp / -timestamp."
        ),
    )

    class Meta(WorkflowRunListParamSerializer.Meta):
        fields = list(WorkflowRunListParamSerializer.Meta.fields) + [
            "start_time",
            "end_time",
            "is_ongoing",
            "status",
            api_settings.SEARCH_PARAM,
            api_settings.ORDERING_PARAM,
        ]


class WorkflowRunSerializer(WorkflowRunBaseSerializer):
    from .workflow import WorkflowMinSerializer

    workflow = WorkflowMinSerializer(read_only=True)

    class Meta(OrcabusIdSerializerMetaMixin):
        model = WorkflowRun
        exclude = ["libraries"]


class WorkflowRunDetailSerializer(WorkflowRunBaseSerializer):
    from .library import LibrarySerializer
    from .workflow import WorkflowSerializer
    from .analysis_run import AnalysisRunSerializer

    libraries = LibrarySerializer(many=True, read_only=True)
    workflow = WorkflowSerializer(read_only=True)
    analysis_run = AnalysisRunSerializer(read_only=True)
    current_state = serializers.SerializerMethodField()

    class Meta(OrcabusIdSerializerMetaMixin):
        model = WorkflowRun
        fields = "__all__"
