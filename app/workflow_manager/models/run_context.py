from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager


class RunContextStatus(models.TextChoices):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class RunContextUseCase(models.TextChoices):
    COMPUTE = "COMPUTE"
    STORAGE = "STORAGE"


class RunContextManager(OrcaBusBaseManager):
    pass


class RunContext(OrcaBusBaseModel):
    class Meta:
        unique_together = ["name", "usecase"]

    orcabus_id = OrcaBusIdField(primary_key=True, prefix='rnx')
    name = models.CharField(max_length=255)
    usecase = models.CharField(max_length=255, choices=RunContextUseCase)

    description = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=255, choices=RunContextStatus, default=RunContextStatus.ACTIVE)

    objects = RunContextManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, name: {self.name}, usecase: {self.usecase}"
