from enum import Enum

from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager


class WorkflowRunContextStatus(models.TextChoices):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class WorkflowRunContextUseCase(Enum):
    COMPUTE = "COMPUTE"
    STORAGE = "STORAGE"


class WorkflowRunContextManager(OrcaBusBaseManager):
    pass


class WorkflowRunContext(OrcaBusBaseModel):
    class Meta:
        unique_together = ["name", "usecase"]

    orcabus_id = OrcaBusIdField(primary_key=True, prefix='wrx')
    name = models.CharField(max_length=255)
    usecase = models.CharField(max_length=255)

    description = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=255, choices=WorkflowRunContextStatus, default=WorkflowRunContextStatus.ACTIVE)

    objects = WorkflowRunContextManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, name: {self.name}, usecase: {self.usecase}"
