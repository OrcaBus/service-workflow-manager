from workflow_manager.models import RunContext
from workflow_manager.serializers.base import SerializersBase, OptionalFieldsMixin, OrcabusIdSerializerMetaMixin


class RunContextBaseSerializer(SerializersBase):
    pass


class RunContextListParamSerializer(OptionalFieldsMixin, RunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = RunContext
        fields = "__all__"


class RunContextMinSerializer(RunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = RunContext
        fields = ["orcabus_id", "name", "usecase"]


class RunContextSerializer(RunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = RunContext
        fields = "__all__"


class UpdatableRunContextSerializer(RunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = RunContext
        fields = ["description", "status"]

    def update(self, instance, validated_data):
        # If the description is just an empty string, skip.
        if validated_data.get("description", None) == "":
            validated_data.pop("description")

        return super().update(instance, validated_data)
