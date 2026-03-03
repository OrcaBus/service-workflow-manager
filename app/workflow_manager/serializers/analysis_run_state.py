from workflow_manager.serializers.base import SerializersBase, OrcabusIdSerializerMetaMixin
from workflow_manager.models import AnalysisRunState


class AnalysisRunStateBaseSerializer(SerializersBase):
    pass


class AnalysisRunStateMinSerializer(AnalysisRunStateBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRunState
        fields = ["orcabus_id", "status", "timestamp", "comment"]


class AnalysisRunStateSerializer(AnalysisRunStateBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRunState
        fields = "__all__"
