from workflow_manager.models import AnalysisRun
from workflow_manager.serializers.base import SerializersBase, OptionalFieldsMixin, OrcabusIdSerializerMetaMixin


class AnalysisRunBaseSerializer(SerializersBase):
    pass


class AnalysisRunListParamSerializer(OptionalFieldsMixin, AnalysisRunBaseSerializer, ):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRun
        fields = "__all__"


class AnalysisRunSerializer(AnalysisRunBaseSerializer):
    from .analysis import AnalysisMinSerializer
    from .analysis_context import AnalysisContextMinSerializer

    analysis = AnalysisMinSerializer(read_only=True)
    storage_context = AnalysisContextMinSerializer(read_only=True)
    compute_context = AnalysisContextMinSerializer(read_only=True)

    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRun
        exclude = ["libraries"]


class AnalysisRunDetailSerializer(AnalysisRunBaseSerializer):
    from .library import LibrarySerializer
    from .analysis import AnalysisSerializer
    from .analysis_context import AnalysisContextSerializer

    libraries = LibrarySerializer(many=True, read_only=True)
    analysis = AnalysisSerializer(read_only=True)
    storage_context = AnalysisContextSerializer(read_only=True)
    compute_context = AnalysisContextSerializer(read_only=True)

    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRun
        fields = "__all__"
