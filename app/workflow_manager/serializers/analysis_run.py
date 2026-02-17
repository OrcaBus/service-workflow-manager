from rest_framework import serializers

from workflow_manager.models import AnalysisRun, Library, Analysis, RunContext, Readset, WorkflowRun
from workflow_manager.serializers.base import (
    SerializersBase,
    OptionalFieldsMixin,
    OrcabusIdSerializerMetaMixin,
    OrcabusIdListUtils,
    OrcabusIdListField,
)
from .analysis_run_state import AnalysisRunStateMinSerializer, AnalysisRunStateSerializer


class AnalysisRunBaseSerializer(SerializersBase):
    # include the current state
    current_state = serializers.SerializerMethodField()

    def get_current_state(self, obj) -> dict:
        latest_state = obj.get_latest_state()
        return AnalysisRunStateMinSerializer(latest_state).data if latest_state else None


class AnalysisRunListParamSerializer(OptionalFieldsMixin, AnalysisRunBaseSerializer, ):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRun
        fields = "__all__"


class AnalysisRunSerializer(AnalysisRunBaseSerializer):
    from .analysis import AnalysisMinSerializer
    from .run_context import RunContextMinSerializer
    from .readset import ReadsetMinSerializer

    analysis = AnalysisMinSerializer(read_only=True)
    contexts = RunContextMinSerializer(many=True, read_only=True)
    readsets = ReadsetMinSerializer(many=True, read_only=True)
    # current_state from AnalysisRunBaseSerializer (SerializerMethodField)

    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRun
        fields = "__all__"

class AnalysisRunDetailSerializer(AnalysisRunBaseSerializer):
    from .library import LibrarySerializer
    from .analysis import AnalysisSerializer
    from .run_context import RunContextSerializer
    from .readset import ReadsetSerializer

    libraries = LibrarySerializer(many=True, read_only=True)
    analysis = AnalysisSerializer(read_only=True)
    contexts = RunContextSerializer(many=True, read_only=True)
    readsets = ReadsetSerializer(many=True, read_only=True)
    # current_state from AnalysisRunBaseSerializer (latest state)
    states = serializers.SerializerMethodField()

    def get_states(self, obj) -> list:
        all_states = obj.states.order_by("timestamp")
        return AnalysisRunStateSerializer(all_states, many=True).data if all_states else []

    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRun
        fields = "__all__"


class WritableAnalysisRunSerializer(AnalysisRunBaseSerializer):
    """
    Serializer for creating and updating AnalysisRun.
    Accepts orcabus_ids for libraries, analysis, contexts, and readsets.
    For PATCH: empty/blank fields are optional (omit from update).
    """

    libraries = OrcabusIdListField(
        child=serializers.CharField(allow_blank=True),
        help_text="List of Library orcabus_ids",
        required=False,
    )
    analysis = serializers.CharField(
        help_text="Analysis orcabus_id",
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    contexts = OrcabusIdListField(
        child=serializers.CharField(allow_blank=True),
        help_text="List of RunContext orcabus_ids",
        required=False,
    )
    readsets = OrcabusIdListField(
        child=serializers.CharField(allow_blank=True),
        help_text="List of Readset orcabus_ids",
        required=False,
    )
    workflow_runs = OrcabusIdListField(
        child=serializers.CharField(allow_blank=True),
        help_text="List of WorkflowRun orcabus_ids to link to this AnalysisRun. Updates workflow_run.analysis_run.",
        required=False,
    )

    class Meta(OrcabusIdSerializerMetaMixin):
        model = AnalysisRun
        fields = ["analysis_run_name", "comment", "analysis", "libraries", "contexts", "readsets", "workflow_runs"]
        extra_kwargs = {
            **OrcabusIdSerializerMetaMixin.extra_kwargs,
            "analysis_run_name": {"required": False, "allow_blank": True},
            "comment": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        if self.instance is None:  # create
            for field in ("libraries", "contexts", "readsets"):
                if not attrs.get(field):
                    raise serializers.ValidationError(
                        {field: "This field is required when creating an AnalysisRun."}
                    )
            if not (attrs.get("analysis_run_name") or "").strip():
                raise serializers.ValidationError(
                    {"analysis_run_name": "This field is required when creating an AnalysisRun."}
                )
        if attrs.get("analysis"):
            self._resolve_analysis(attrs["analysis"])
        for field, model in [
            ("libraries", Library),
            ("contexts", RunContext),
            ("readsets", Readset),
            ("workflow_runs", WorkflowRun),
        ]:
            if attrs.get(field):
                self._ids_to_queryset(model, attrs[field], field)
        return attrs

    def _ids_to_queryset(self, model, ids, field_name):
        """Resolve IDs to queryset; validate all exist. Raise ValidationError if any missing."""
        ids = OrcabusIdListUtils.normalize(ids)
        if not ids:
            return model.objects.none()
        qs = model.objects.filter(pk__in=ids)
        found = set(qs.values_list("pk", flat=True))
        missing = set(ids) - found
        if missing:
            raise serializers.ValidationError(
                {field_name: f"The following {field_name} do not exist: {', '.join(missing)}."}
            )
        return qs

    def _resolve_analysis(self, analysis_id):
        """Resolve analysis_id to Analysis or None. Raise ValidationError if invalid."""
        if not analysis_id or (isinstance(analysis_id, str) and not analysis_id.strip()):
            return None
        try:
            return Analysis.objects.get(pk=analysis_id.strip())
        except Analysis.DoesNotExist:
            raise serializers.ValidationError(
                {"analysis": f"Analysis with orcabus_id '{analysis_id}' does not exist."}
            )

    def _set_relations(self, instance, relations_data):
        """Set M2M and FK relations from {field: ids} dict."""
        if "analysis" in relations_data:
            instance.analysis = self._resolve_analysis(relations_data["analysis"])
            instance.save(update_fields=["analysis"])
        for field, model in [
            ("libraries", Library),
            ("contexts", RunContext),
            ("readsets", Readset),
        ]:
            if field in relations_data:
                getattr(instance, field).set(
                    self._ids_to_queryset(model, relations_data[field], field)
                )
        if "workflow_runs" in relations_data:
            ids = OrcabusIdListUtils.normalize(relations_data["workflow_runs"])
            if ids:
                WorkflowRun.objects.filter(pk__in=ids).update(analysis_run=instance)

    def create(self, validated_data):
        relations = {
            "libraries": OrcabusIdListUtils.normalize(validated_data.pop("libraries", [])),
            "contexts": OrcabusIdListUtils.normalize(validated_data.pop("contexts", [])),
            "readsets": OrcabusIdListUtils.normalize(validated_data.pop("readsets", [])),
            "analysis": validated_data.pop("analysis", None),
            "workflow_runs": OrcabusIdListUtils.normalize(validated_data.pop("workflow_runs", [])),
        }
        instance = super().create(validated_data)
        self._set_relations(instance, relations)
        return instance

    def _is_empty_partial_value(self, value):
        """For partial update: treat as empty (skip) if blank/empty."""
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        if isinstance(value, list) and not value:
            return True
        return False

    def update(self, instance, validated_data):
        # For partial update: skip empty values (don't overwrite with blank)
        for field in list(validated_data.keys()):
            if self._is_empty_partial_value(validated_data[field]):
                validated_data.pop(field, None)

        relations = {}
        if "analysis" in validated_data:
            relations["analysis"] = validated_data.pop("analysis")
        for field in ("libraries", "contexts", "readsets", "workflow_runs"):
            if field in validated_data:
                relations[field] = OrcabusIdListUtils.normalize(validated_data.pop(field))
        self._set_relations(instance, relations)
        return super().update(instance, validated_data)
