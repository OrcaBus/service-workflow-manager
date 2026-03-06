from workflow_manager.serializers.base import SerializersBase, OrcabusIdSerializerMetaMixin
from workflow_manager.models import Comment
from rest_framework import serializers


class CommentBaseSerializer(SerializersBase):
    pass


class CommentMinSerializer(CommentBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Comment
        fields = ["orcabus_id", "text", "created_at", 'updated_at']


class CommentSerializer(CommentBaseSerializer):
    is_deleted = serializers.BooleanField(required=False, default=False)
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Comment
        fields = "__all__"
