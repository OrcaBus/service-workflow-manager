from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager
from workflow_manager.models import AnalysisRun


class AnalysisRunReadsetManager(OrcaBusBaseManager):
    pass


class AnalysisRunReadset(OrcaBusBaseModel):

    orcabus_id = OrcaBusIdField(primary_key=True, prefix='fqr')
    analysis_run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE, related_name='readsets')

    # TODO: decide what we want to do with the rgid
    # # rgid = models.CharField(max_length=255)
    # lane = models.CharField(max_length=255)
    # index = models.CharField(max_length=255)
    # instrument_run_id = models.CharField(max_length=255)
    library_id = models.CharField(max_length=255)
    library_oid = models.CharField(max_length=255)

    objects = AnalysisRunReadsetManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}"


