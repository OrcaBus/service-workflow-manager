from workflow_manager.serializers.base import SerializersBase, OrcabusIdSerializerMetaMixin
from workflow_manager.models import Comment
from workflow_manager.models.comment import CommentSeverity
from rest_framework import serializers

class CommentCreateRequestSerializer(serializers.Serializer):
    """Request body for POST .../comment/ (OpenAPI + validation)."""

    text = serializers.CharField()
    created_by = serializers.CharField()
    severity = serializers.ChoiceField(
        choices=CommentSeverity.choices,
        required=False,
        help_text="Optional; defaults to INFO.",
    )

class CommentUpdateRequestSerializer(serializers.Serializer):
    """Request body for PATCH .../comment/{id}/ (OpenAPI + validation)."""

    text = serializers.CharField(required=False)
    created_by = serializers.CharField(required=False)
    severity = serializers.ChoiceField(
        choices=CommentSeverity.choices,
        required=False,
        help_text="Optional; defaults to INFO.",
    )


class CommentBaseSerializer(SerializersBase):
    pass


class CommentMinSerializer(CommentBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Comment
        fields = ["orcabus_id", "text", "severity", "created_at", "updated_at"]


class CommentSerializer(CommentBaseSerializer):
    is_deleted = serializers.BooleanField(required=False, default=False)
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Comment
        fields = "__all__"
