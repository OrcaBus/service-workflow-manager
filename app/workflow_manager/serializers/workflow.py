from workflow_manager.models import Workflow
from workflow_manager.serializers.base import SerializersBase, OptionalFieldsMixin, OrcabusIdSerializerMetaMixin


class WorkflowBaseSerializer(SerializersBase):
    pass


class WorkflowListParamSerializer(OptionalFieldsMixin, WorkflowBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Workflow
        fields = "__all__"


class WorkflowMinSerializer(WorkflowBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Workflow
        fields = ["orcabus_id", "workflow_name", "workflow_version", "execution_engine"]


class WorkflowSerializer(WorkflowBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Workflow
        fields = "__all__"


class UpdatableWorkflowSerializer(WorkflowBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Workflow
        fields = ["execution_engine_pipeline_id"]

    def update(self, instance, validated_data):
        # If the execution_engine_pipeline_id is just an empty string, skip.
        if validated_data.get("execution_engine_pipeline_id", None) == "":
            validated_data.pop("execution_engine_pipeline_id")

        return super().update(instance, validated_data)
