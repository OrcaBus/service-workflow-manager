from workflow_manager.serializers.base import SerializersBase, OrcabusIdSerializerMetaMixin
from workflow_manager.models import Readset


class ReadsetBaseSerializer(SerializersBase):
    pass


class ReadsetMinSerializer(ReadsetBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Readset
        fields = ["orcabus_id", "rgid", "library_id", "library_orcabus_id"]


class ReadsetSerializer(ReadsetBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = Readset
        fields = "__all__"
