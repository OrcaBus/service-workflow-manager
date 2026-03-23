from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager


class RunContextStatus(models.TextChoices):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class RunContextPlatform(models.TextChoices):
    ICAV2 = "ICAV2"
    SEQERA = "SEQERA"
    AWS_BATCH = "AWS_BATCH"
    AWS_ECS = "AWS_ECS"


class RunContextUseCase(models.TextChoices):
    COMPUTE = "COMPUTE"
    STORAGE = "STORAGE"
    EXECUTION_MODE = "EXECUTION_MODE"


class RunContextManager(OrcaBusBaseManager):
    pass


class RunContext(OrcaBusBaseModel):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "usecase", "platform"],
                nulls_distinct=False,
                name="unique_runcontext_name_usecase_platform",
            )
        ]

    orcabus_id = OrcaBusIdField(primary_key=True, prefix='rnx')
    name = models.CharField(max_length=255)
    usecase = models.CharField(max_length=255, choices=RunContextUseCase)

    description = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=255, choices=RunContextStatus, default=RunContextStatus.ACTIVE)

    platform = models.CharField(
        max_length=255,
        choices=RunContextPlatform,
        null=True,
        blank=True,
    )
    data = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        default=None,
    )

    objects = RunContextManager()

    def clean(self):
        super().clean()
        if self.data == {}:
            self.data = None
        if self.usecase == RunContextUseCase.EXECUTION_MODE and self.platform is not None:
            raise ValidationError(
                {"platform": "platform must be NULL for EXECUTION_MODE contexts."}
            )

    def __str__(self):
        return f"ID: {self.orcabus_id}, name: {self.name}, usecase: {self.usecase}, platform: {self.platform}"
