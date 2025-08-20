from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager


class AnalysisContextStatus(models.TextChoices):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class AnalysisContextUseCase(models.TextChoices):
    COMPUTE = "COMPUTE"
    STORAGE = "STORAGE"


class AnalysisContextManager(OrcaBusBaseManager):
    pass


class AnalysisContext(OrcaBusBaseModel):
    class Meta:
        unique_together = ["name", "usecase"]

    orcabus_id = OrcaBusIdField(primary_key=True, prefix='anx')
    name = models.CharField(max_length=255)
    usecase = models.CharField(max_length=255, choices=AnalysisContextUseCase)

    description = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=255, choices=AnalysisContextStatus, default=AnalysisContextStatus.ACTIVE)

    objects = AnalysisContextManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, name: {self.name}, usecase: {self.usecase}"
