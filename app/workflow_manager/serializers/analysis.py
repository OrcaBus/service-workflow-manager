from rest_framework import serializers
from rest_framework.settings import api_settings

from workflow_manager.models import Analysis, AnalysisContext, Workflow, AnalysisStatus
from workflow_manager.serializers.analysis_context import AnalysisContextSerializer
from workflow_manager.serializers.base import (
    SerializersBase,
    OptionalFieldsMixin,
    OrcabusIdSerializerMetaMixin,
    OrcabusIdListUtils,
)
from workflow_manager.serializers.workflow import WorkflowSerializer


class AnalysisBaseSerializer(SerializersBase):
    pass


class AnalysisListParamSerializer(OptionalFieldsMixin, AnalysisBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Analysis
        fields = "__all__"


class AnalysisListQueryParamSerializer(AnalysisListParamSerializer):
    """Full query parameter schema for analysis list and stats endpoints (OpenAPI)."""

    status = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        choices=AnalysisStatus.choices,
        help_text="Filter by status (e.g. ACTIVE, INACTIVE).",
    )
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Substring search on analysis name, version, description.",
    )
    ordering = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Sort order: e.g. analysis_name, -analysis_name, status, -status.",
    )

    class Meta(AnalysisListParamSerializer.Meta):
        fields = [
            "orcabus_id", "analysis_name", "analysis_version", "description",
            "status",
            api_settings.SEARCH_PARAM, api_settings.ORDERING_PARAM,
        ]


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

    def update(self, instance, validated_data):
        if validated_data.get("description", None) == "":
            validated_data.pop("description")

        if validated_data.get("contexts", None):
            context_ids = OrcabusIdListUtils.normalize(validated_data.pop("contexts"))
            instance.contexts.set(AnalysisContext.objects.filter(pk__in=context_ids))

        if validated_data.get("workflows", None):
            workflow_ids = OrcabusIdListUtils.normalize(validated_data.pop("workflows"))
            instance.workflows.set(Workflow.objects.filter(pk__in=workflow_ids))

        return super().update(instance, validated_data)
