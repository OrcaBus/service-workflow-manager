from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager


class PayloadManager(OrcaBusBaseManager):
    pass


class Payload(OrcaBusBaseModel):
    class Meta:
        unique_together = ["payload_ref_id", "version"]

    orcabus_id = OrcaBusIdField(primary_key=True, prefix='pld')
    payload_ref_id = models.CharField(max_length=255)
    version = models.CharField(max_length=255)
    data = models.JSONField(encoder=DjangoJSONEncoder)

    objects = PayloadManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, payload_ref_id: {self.payload_ref_id}"
