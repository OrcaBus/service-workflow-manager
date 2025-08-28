from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager


class ExecutionEngine(models.TextChoices):
    UNKNOWN = "Unknown"
    ICA = "ICA"
    SEQERA = "SEQERA"
    AWS_BATCH = "AWS_BATCH"
    AWS_ECS = "AWS_ECS"
    AWS_EKS = "AWS_EKS"


class ValidationState(models.TextChoices):
    UNVALIDATED = "UNVALIDATED"
    VALIDATED = "VALIDATED"
    DEPRECATED = "DEPRECATED"
    FAILED = "FAILED"


class WorkflowManager(OrcaBusBaseManager):
    pass


class Workflow(OrcaBusBaseModel):
    class Meta:
        # a combo of this gives us human-readable pipeline id
        unique_together = ["name", "version", "code_version", "execution_engine"]

    orcabus_id = OrcaBusIdField(primary_key=True, prefix='wfl')
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=255)
    # See https://github.com/OrcaBus/service-workflow-manager/issues/95
    code_version = models.CharField(max_length=255, default="0.0.0")
    execution_engine = models.CharField(max_length=255, choices=ExecutionEngine)

    # definition from an external system (as known to the execution engine)
    execution_engine_pipeline_id = models.CharField(max_length=255, default="Unknown")

    # may need this to differentiate with workflows are
    # - unvalidated
    # - validated
    # - deprecated
    # - failed (validation) - although those should probably never be used and deleted directly
    # e.g. support testing in production, so unvalidated workflows are not used
    validation_state = models.CharField(max_length=255, choices=ValidationState, default=ValidationState.VALIDATED)  # FIXME revert to UNVALIDATED once initial migration completed

    objects = WorkflowManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, name: {self.name}, version: {self.version}"
