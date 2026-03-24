from rest_framework import serializers

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
    implemented in WorkflowRunViewSet and WorkflowRunStatsViewSet.
    """

    start_time = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="ISO 8601 datetime; start of range on latest state timestamp (use with end_time).",
    )
    end_time = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="ISO 8601 datetime; end of range on latest state timestamp (use with start_time).",
    )
    is_ongoing = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="If 'true', only runs whose latest state is not terminal.",
    )
    status = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Filter by latest state status (e.g. SUCCEEDED, FAILED).",
    )
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Search workflow run name, comment, library_id, orcabus_id, and workflow name.",
    )
    order_by = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Sort by latest state time: 'timestamp' (ascending) or '-timestamp' (descending).",
    )

    class Meta(WorkflowRunListParamSerializer.Meta):
        fields = WorkflowRunListParamSerializer.Meta.fields + [
            "start_time",
            "end_time",
            "is_ongoing",
            "status",
            "search",
            "order_by",
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


class WorkflowRunCountByStatusSerializer(serializers.Serializer):
    all = serializers.IntegerField()
    succeeded = serializers.IntegerField()
    aborted = serializers.IntegerField()
    failed = serializers.IntegerField()
    resolved = serializers.IntegerField()
    ongoing = serializers.IntegerField()
    deprecated = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass
