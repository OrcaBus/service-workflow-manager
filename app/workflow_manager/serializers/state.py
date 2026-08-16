from workflow_manager.serializers.base import (
    SerializersBase,
    OrcabusIdSerializerMetaMixin,
    OrcabusIdListField,
)
from workflow_manager.models import State
from rest_framework import serializers


class StateBaseSerializer(SerializersBase):
    created_by = serializers.CharField(read_only=True, allow_null=True)


class StateMinSerializer(StateBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = State
        fields = ["orcabus_id", "status", "timestamp", "created_by"]


class StateSerializer(StateBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = State
        fields = "__all__"


class StateUpdateRequestSerializer(serializers.Serializer):
    """
    Schema contract for PATCH /state/{id}.
    Request accepts only `comment`.
    """

    comment = serializers.CharField(required=True, allow_blank=False)


class StateTransitionRequestSerializer(serializers.Serializer):
    """
    Schema contract for POST /workflowrun/state/{transition}/.
    The endpoint determines the target state. The request body contains
    workflowrunOrcabusIds (list or CSV string) and comment.
    """

    workflowrun_orcabus_ids = OrcabusIdListField(
        child=serializers.CharField(allow_blank=False),
        required=True,
        allow_empty=False,
    )
    comment = serializers.CharField(required=True, allow_blank=False)


class StateTransitionValidationErrorSerializer(serializers.Serializer):
    """Field-level validation errors returned for an invalid transition request."""

    workflowrun_orcabus_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
    comment = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
    non_field_errors = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )


class StateTransitionFailureSerializer(serializers.Serializer):
    workflowrun_orcabus_id = serializers.CharField()
    reason = serializers.CharField()
    detail = serializers.CharField()
    error = serializers.CharField(required=False)


class StateTransitionResponseSerializer(serializers.Serializer):
    """
    Schema contract for workflow-run state transition responses.
    JSON responses use camelCase (createdCount, workflowrunOrcabusIds, failedCount).
    """

    created_count = serializers.IntegerField()
    workflowrun_orcabus_ids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
    )
    failed_count = serializers.IntegerField(default=0)
    failures = StateTransitionFailureSerializer(
        many=True,
        required=False,
    )
