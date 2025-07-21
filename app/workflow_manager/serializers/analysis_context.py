from workflow_manager.models import AnalysisContext
from workflow_manager.serializers.base import SerializersBase, OptionalFieldsMixin, OrcabusIdSerializerMetaMixin


class AnalysisContextBaseSerializer(SerializersBase):
    pass


class AnalysisContextListParamSerializer(OptionalFieldsMixin, AnalysisContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisContext
        fields = "__all__"


class AnalysisContextMinSerializer(AnalysisContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisContext
        fields = ["orcabus_id", "name", "usecase"]


class AnalysisContextSerializer(AnalysisContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisContext
        fields = "__all__"


class UpdatableAnalysisContextSerializer(AnalysisContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisContext
        fields = ["description", "status"]

    def update(self, instance, validated_data):
        # If the description is just an empty string, skip.
        if validated_data.get("description", None) == "":
            validated_data.pop("description")

        return super().update(instance, validated_data)
