from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager


class ReadsetManager(OrcaBusBaseManager):
    pass


class Readset(OrcaBusBaseModel):

    orcabus_id = OrcaBusIdField(primary_key=True, prefix='lib')
    rgid = models.CharField(max_length=255)

    objects = ReadsetManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, rgid: {self.rgid}"
