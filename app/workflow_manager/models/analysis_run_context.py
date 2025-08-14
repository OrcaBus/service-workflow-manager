from enum import Enum

from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager


class AnalysisRunContextStatus(models.TextChoices):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class AnalysisRunContextUseCase(Enum):
    COMPUTE = "COMPUTE"
    STORAGE = "STORAGE"


class AnalysisRunContextManager(OrcaBusBaseManager):
    pass


class AnalysisRunContext(OrcaBusBaseModel):
    class Meta:
        unique_together = ["name", "usecase"]

    orcabus_id = OrcaBusIdField(primary_key=True, prefix='arx')
    name = models.CharField(max_length=255)
    usecase = models.CharField(max_length=255)

    description = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=255, choices=AnalysisRunContextStatus, default=AnalysisRunContextStatus.ACTIVE)

    objects = AnalysisRunContextManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, name: {self.name}, usecase: {self.usecase}"
