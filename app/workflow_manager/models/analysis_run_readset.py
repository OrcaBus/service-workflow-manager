from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager
from workflow_manager.models import AnalysisRun, Library


class AnalysisRunReadsetManager(OrcaBusBaseManager):
    pass


class AnalysisRunReadset(OrcaBusBaseModel):

    orcabus_id = OrcaBusIdField(primary_key=True, prefix='lib')
    rgid = models.CharField(max_length=255)
    analysis_run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE)
    library = models.ForeignKey(Library, on_delete=models.CASCADE)

    objects = AnalysisRunReadsetManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, rgid: {self.rgid}"
