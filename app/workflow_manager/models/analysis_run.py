from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.analysis import Analysis
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager
from workflow_manager.models.library import Library
from workflow_manager.models.readset import Readset
from workflow_manager.models.run_context import RunContext


class AnalysisRunManager(OrcaBusBaseManager):
    pass


class AnalysisRun(OrcaBusBaseModel):
    orcabus_id = OrcaBusIdField(primary_key=True, prefix='anr')
    analysis_run_name = models.CharField(max_length=255)
    comment = models.CharField(max_length=255, null=True, blank=True)

    analysis = models.ForeignKey(Analysis, null=True, blank=True, on_delete=models.SET_NULL)
    libraries = models.ManyToManyField(Library)
    contexts = models.ManyToManyField(RunContext)
    readsets = models.ManyToManyField(Readset)

    objects = AnalysisRunManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, analysis_run_name: {self.analysis_run_name}"

    def get_all_states(self):
        # retrieve all states (DB records rather than a queryset)
        return list(self.states.all())  # TODO: ensure order by timestamp ?

    def get_latest_state(self):
        # retrieve all related states and get the latest one
        return self.states.order_by('-timestamp').first()
