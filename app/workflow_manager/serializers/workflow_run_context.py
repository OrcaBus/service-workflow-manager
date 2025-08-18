from workflow_manager.models.workflow_run_context import WorkflowRunContext
from workflow_manager.serializers.base import SerializersBase, OptionalFieldsMixin, OrcabusIdSerializerMetaMixin


class WorkflowRunContextBaseSerializer(SerializersBase):
    pass


class WorkflowRunContextListParamSerializer(OptionalFieldsMixin, WorkflowRunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = WorkflowRunContext
        fields = "__all__"


class WorkflowRunContextMinSerializer(WorkflowRunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = WorkflowRunContext
        fields = ["orcabus_id", "name", "usecase"]


class WorkflowRunContextSerializer(WorkflowRunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = WorkflowRunContext
        fields = "__all__"


class UpdatableWorkflowRunContextSerializer(WorkflowRunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = WorkflowRunContext
        fields = ["description", "status"]

    def update(self, instance, validated_data):
        # If the description is just an empty string, skip.
        if validated_data.get("description", None) == "":
            validated_data.pop("description")

        return super().update(instance, validated_data)
