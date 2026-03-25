from workflow_manager.serializers.base import SerializersBase, OrcabusIdSerializerMetaMixin
from workflow_manager.models import State
from rest_framework import serializers


class OrcabusIdListField(serializers.ListField):
    """
    Accept either:
    - JSON array/list of IDs
    - comma-separated string of IDs (e.g. form payload)
    """

    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [item.strip() for item in data.split(",") if item.strip()]
        elif isinstance(data, (list, tuple)):
            expanded_data = []
            for item in data:
                if isinstance(item, str) and "," in item:
                    expanded_data.extend([token.strip() for token in item.split(",") if token.strip()])
                else:
                    expanded_data.append(item)
            data = expanded_data
        return super().to_internal_value(data)


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


class StateBatchTransitionRequestSerializer(serializers.Serializer):
    """
    Schema contract for POST /workflowrun/state/batch-state-transition/.
    Request body: workflowrun_orcabus_ids (list or CSV string), status, comment.
    """

    workflowrun_orcabus_ids = OrcabusIdListField(
        child=serializers.CharField(allow_blank=False),
        required=True,
        allow_empty=False,
    )
    status = serializers.CharField(required=True, allow_blank=False)
    comment = serializers.CharField(required=True, allow_blank=False)
