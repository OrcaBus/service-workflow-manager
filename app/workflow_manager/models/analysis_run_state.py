from enum import Enum
from typing import List

from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager
from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager.models.utils import Status


class AnalysisRunStateManager(OrcaBusBaseManager):
    pass


class AnalysisRunState(OrcaBusBaseModel):
    class Meta:
        unique_together = ["analysis_run", "status", "timestamp"]

    # --- mandatory fields
    orcabus_id = OrcaBusIdField(primary_key=True, prefix='ars')
    status = models.CharField(max_length=255)  # TODO: How and where to enforce conventions?
    timestamp = models.DateTimeField()
    comment = models.CharField(max_length=255, null=True, blank=True)

    analysis_run = models.ForeignKey(AnalysisRun, related_name='states', on_delete=models.CASCADE)

    objects = AnalysisRunStateManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, status: {self.status}"

    def is_terminal(self) -> bool:
        return Status.is_terminal(str(self.status))

    def is_draft(self) -> bool:
        return Status.is_draft(str(self.status))

    def is_ready(self) -> bool:
        return Status.is_ready(str(self.status))

    def is_running(self) -> bool:
        return Status.is_running(str(self.status))
