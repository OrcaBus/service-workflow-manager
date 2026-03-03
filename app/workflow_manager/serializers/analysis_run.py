from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

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
