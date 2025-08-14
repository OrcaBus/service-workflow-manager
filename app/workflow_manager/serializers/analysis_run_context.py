from workflow_manager.models import AnalysisRunContext
from workflow_manager.serializers.base import SerializersBase, OptionalFieldsMixin, OrcabusIdSerializerMetaMixin


class AnalysisRunContextBaseSerializer(SerializersBase):
    pass


class AnalysisRunContextListParamSerializer(OptionalFieldsMixin, AnalysisRunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRunContext
        fields = "__all__"


class AnalysisRunContextMinSerializer(AnalysisRunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRunContext
        fields = ["orcabus_id", "name", "usecase"]


class AnalysisRunContextSerializer(AnalysisRunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRunContext
        fields = "__all__"


class UpdatableAnalysisRunContextSerializer(AnalysisRunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRunContext
        fields = ["description", "status"]

    def update(self, instance, validated_data):
        # If the description is just an empty string, skip.
        if validated_data.get("description", None) == "":
            validated_data.pop("description")

        return super().update(instance, validated_data)
