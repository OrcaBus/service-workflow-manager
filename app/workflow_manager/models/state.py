from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager
from workflow_manager.models.payload import Payload
from workflow_manager.models.workflow_run import WorkflowRun
from workflow_manager.models.common import Status



class StateManager(OrcaBusBaseManager):
    pass


class State(OrcaBusBaseModel):
    class Meta:
        unique_together = ["workflow_run", "status", "timestamp"]

    # --- mandatory fields
    orcabus_id = OrcaBusIdField(primary_key=True, prefix='stt')
    status = models.CharField(max_length=255)  # TODO: How and where to enforce conventions?
    timestamp = models.DateTimeField()
    comment = models.CharField(max_length=255, null=True, blank=True)

    workflow_run = models.ForeignKey(WorkflowRun, related_name='states', on_delete=models.CASCADE)
    # Link to workflow run payload data
    payload = models.ForeignKey(Payload, null=True, blank=True, on_delete=models.SET_NULL)

    objects = StateManager()

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
