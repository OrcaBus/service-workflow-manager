from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.settings import api_settings

from workflow_manager.models import Workflow, ValidationState
from workflow_manager.serializers.base import SerializersBase, OptionalFieldsMixin, OrcabusIdSerializerMetaMixin


class WorkflowBaseSerializer(SerializersBase):
    pass


class WorkflowHistorySerializer(WorkflowBaseSerializer):
    """Serializer for workflow version history records."""

    class Meta(OrcabusIdSerializerMetaMixin):
        model = Workflow
        fields = [
            "orcabus_id",
            "name",
            "version",
            "code_version",
            "execution_engine",
            "execution_engine_pipeline_id",
            "validation_state",
        ]


class WorkflowListSerializer(WorkflowBaseSerializer):
    """Serializer for workflow list API with history of all versions."""

    history = serializers.SerializerMethodField()

    @extend_schema_field(WorkflowHistorySerializer(many=True))
    def get_history(self, obj):
        history_records = self.context.get("history_map", {}).get(obj.orcabus_id, [])
        return WorkflowHistorySerializer(history_records, many=True).data

    class Meta(OrcabusIdSerializerMetaMixin):
        model = Workflow
        fields = [
            "orcabus_id",
            "name",
            "version",
            "code_version",
            "execution_engine",
            "execution_engine_pipeline_id",
            "validation_state",
            "history",
        ]


class WorkflowListParamSerializer(OptionalFieldsMixin, WorkflowBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Workflow
        fields = "__all__"


class WorkflowListQueryParamSerializer(WorkflowListParamSerializer):
    """Full query parameter schema for workflow list and stats endpoints (OpenAPI)."""

    status = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        choices=ValidationState.choices,
        help_text="Filter by validation state (e.g. VALIDATED, UNVALIDATED, DEPRECATED, FAILED).",
    )
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Substring search on name, version, code_version, pipeline id.",
    )
    ordering = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Sort order: e.g. name, -name, version, -version, validation_state.",
    )

    class Meta(WorkflowListParamSerializer.Meta):
        fields = [
            "orcabus_id", "name", "version", "code_version",
            "execution_engine", "execution_engine_pipeline_id",
            "status",
            api_settings.SEARCH_PARAM, api_settings.ORDERING_PARAM,
        ]


class WorkflowMinSerializer(WorkflowBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Workflow
        fields = ["orcabus_id", "name", "version", "code_version", "execution_engine"]


class WorkflowSerializer(WorkflowBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Workflow
        fields = "__all__"
