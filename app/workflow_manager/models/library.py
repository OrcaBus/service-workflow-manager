from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from enum import Enum
from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager
from workflow_manager.models import Readset


class AssociationStatus(Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"


class LibraryManager(OrcaBusBaseManager):
    pass


class Library(OrcaBusBaseModel):

    orcabus_id = OrcaBusIdField(primary_key=True, prefix='lib')
    library_id = models.CharField(max_length=255)

    readsets = models.ManyToManyField(Readset,  through="ReadsetAssociation")

    objects = LibraryManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, library_id: {self.library_id}"


class ReadsetAssociationManager(OrcaBusBaseManager):
    pass


class ReadsetAssociation(OrcaBusBaseModel):
    orcabus_id = OrcaBusIdField(primary_key=True)
    library = models.ForeignKey(Library, on_delete=models.CASCADE)
    readset = models.ForeignKey(Readset, on_delete=models.CASCADE)
    association_date = models.DateTimeField()
    status = models.CharField(max_length=255)

    objects = ReadsetAssociationManager()
