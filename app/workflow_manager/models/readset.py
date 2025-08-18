from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager


class ReadsetManager(OrcaBusBaseManager):
    pass


class Readset(OrcaBusBaseModel):
    orcabus_id = OrcaBusIdField(primary_key=True, prefix='fqr')
    rgid = models.CharField(max_length=255)
    library_id = models.CharField(max_length=255)
    library_orcabus_id = models.CharField(max_length=255)

    objects = ReadsetManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}"
