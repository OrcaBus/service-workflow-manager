from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.settings import api_settings

from workflow_manager.models import AnalysisRun
from workflow_manager.serializers.base import (
    SerializersBase,
    OptionalFieldsMixin,
    OrcabusIdSerializerMetaMixin,
)
from .analysis_run_state import AnalysisRunStateMinSerializer, AnalysisRunStateSerializer


class AnalysisRunBaseSerializer(SerializersBase):
    current_state = serializers.SerializerMethodField()

    @extend_schema_field(AnalysisRunStateMinSerializer(allow_null=True))
    def get_current_state(self, obj):
        latest_state = obj.get_latest_state()
        return AnalysisRunStateMinSerializer(latest_state).data if latest_state else None


class AnalysisRunListParamSerializer(OptionalFieldsMixin, AnalysisRunBaseSerializer, ):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRun
        fields = "__all__"


class AnalysisRunListQueryParamSerializer(AnalysisRunListParamSerializer):
    """Full query parameter schema for analysis run list and stats endpoints (OpenAPI)."""

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
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Substring search on analysis run name, comment, analysis name, library ids.",
    )
    ordering = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=(
            "Sort order: model fields such as orcabus_id, -orcabus_id, analysis_run_name; "
            "or latest state time via timestamp / -timestamp."
        ),
    )

    class Meta(AnalysisRunListParamSerializer.Meta):
        fields = [
            "orcabus_id", "analysis_run_name", "comment", "analysis",
            "start_time", "end_time", "is_ongoing", "status",
            api_settings.SEARCH_PARAM, api_settings.ORDERING_PARAM,
        ]


class AnalysisRunSerializer(AnalysisRunBaseSerializer):
    from .analysis import AnalysisMinSerializer
    from .run_context import RunContextMinSerializer
    from .readset import ReadsetMinSerializer

    analysis = AnalysisMinSerializer(read_only=True)
    contexts = RunContextMinSerializer(many=True, read_only=True)
    readsets = ReadsetMinSerializer(many=True, read_only=True)
    # current_state from AnalysisRunBaseSerializer (SerializerMethodField)

    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRun
        fields = "__all__"

class AnalysisRunDetailSerializer(AnalysisRunBaseSerializer):
    from .library import LibrarySerializer
    from .analysis import AnalysisSerializer
    from .run_context import RunContextSerializer
    from .readset import ReadsetSerializer

    libraries = LibrarySerializer(many=True, read_only=True)
    analysis = AnalysisSerializer(read_only=True)
    contexts = RunContextSerializer(many=True, read_only=True)
    readsets = ReadsetSerializer(many=True, read_only=True)
    # current_state from AnalysisRunBaseSerializer (latest state)
    states = serializers.SerializerMethodField()

    @extend_schema_field(AnalysisRunStateSerializer(many=True))
    def get_states(self, obj):
        all_states = obj.states.order_by("timestamp")
        return AnalysisRunStateSerializer(all_states, many=True).data if all_states else []

    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRun
        fields = "__all__"
