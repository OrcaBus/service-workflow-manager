from rest_framework import serializers

from workflow_manager.models import Analysis, AnalysisContext, Workflow
from workflow_manager.serializers.analysis_context import AnalysisContextSerializer
from workflow_manager.serializers.base import SerializersBase, OptionalFieldsMixin, OrcabusIdSerializerMetaMixin
from workflow_manager.serializers.workflow import WorkflowSerializer


class AnalysisBaseSerializer(SerializersBase):
    pass


class AnalysisListParamSerializer(OptionalFieldsMixin, AnalysisBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Analysis
        fields = "__all__"


class AnalysisMinSerializer(AnalysisBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Analysis
        fields = ["orcabus_id", "analysis_name", "analysis_version", "status"]


class AnalysisSerializer(AnalysisBaseSerializer):
    """
    Serializer to define a default representation of an Analysis record,
    mainly used in record listing and retrieval views.
    """

    contexts = AnalysisContextSerializer(many=True, read_only=True)
    workflows = WorkflowSerializer(many=True, read_only=True)

    class Meta(OrcabusIdSerializerMetaMixin):
        model = Analysis
        fields = "__all__"


class UpdatableAnalysisSerializer(AnalysisBaseSerializer):
    class UpdatableIdSerializer(serializers.StringRelatedField):
        def to_internal_value(self, data):
            return data

        def to_representation(self, instance):
            return str(instance.orcabus_id)

    contexts = UpdatableIdSerializer(
        many=True,
        help_text="List of AnalysisContext orcabusId",
        required=False,
    )
    workflows = UpdatableIdSerializer(
        many=True,
        help_text="List of Workflow orcabusId",
        required=False,
    )

    class Meta(OrcabusIdSerializerMetaMixin):
        model = Analysis
        fields = ["contexts", "workflows", "description", "status"]

    @staticmethod
    def handle_swagger_form_payload_format(ids):
        if isinstance(ids, list) and len(ids) == 1:
            if "," in ids[0]:
                return str(ids[0]).split(",")
        return ids

    def update(self, instance, validated_data):
        # If the description is just an empty string, skip.
        if validated_data.get("description", None) == "":
            validated_data.pop("description")

        # If the contexts present, update the analysis contexts linking
        if validated_data.get("contexts", None):
            context_ids = validated_data.pop("contexts")
            context_ids = self.handle_swagger_form_payload_format(context_ids)
            contexts = AnalysisContext.objects.filter(pk__in=context_ids)
            instance.contexts.set(contexts)

        # If the workflows present, update the workflows linking
        if validated_data.get("workflows", None):
            workflow_ids = validated_data.pop("workflows")
            workflow_ids = self.handle_swagger_form_payload_format(workflow_ids)
            workflows = Workflow.objects.filter(pk__in=workflow_ids)
            instance.workflows.set(workflows)

        return super().update(instance, validated_data)
