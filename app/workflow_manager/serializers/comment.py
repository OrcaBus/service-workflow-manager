from workflow_manager.serializers.base import SerializersBase, OrcabusIdSerializerMetaMixin
from workflow_manager.models import Comment


class CommentBaseSerializer(SerializersBase):
    pass


class CommentMinSerializer(CommentBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Comment
        fields = ["orcabus_id", "text", "created_at", 'updated_at']


class CommentSerializer(CommentBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Comment
        fields = "__all__"
