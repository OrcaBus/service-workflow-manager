from workflow_manager.serializers.base import SerializersBase, OrcabusIdSerializerMetaMixin
from workflow_manager.models import State
from rest_framework import serializers


class StateBaseSerializer(SerializersBase):
    pass


class StateMinSerializer(StateBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = State
        fields = ["orcabus_id", "status", "timestamp"]


class StateSerializer(StateBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = State
        fields = "__all__"


class StateCreateRequestSerializer(serializers.Serializer):
    """
    Schema contract for POST /state.
    Request accepts only `status` and `comment`.
    """

    status = serializers.CharField(required=True, allow_blank=False)
    comment = serializers.CharField(required=True, allow_blank=False)



class StateUpdateRequestSerializer(serializers.Serializer):
    """
    Schema contract for PATCH /state/{id}.
    Request accepts only `comment`.
    """

    comment = serializers.CharField(required=True, allow_blank=False)
