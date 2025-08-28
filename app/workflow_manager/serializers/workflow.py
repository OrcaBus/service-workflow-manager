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
        fields = ["orcabus_id", "name", "version", "code_version", "execution_engine"]


class WorkflowSerializer(WorkflowBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Workflow
        fields = "__all__"
