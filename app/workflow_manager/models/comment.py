from django.core.exceptions import ValidationError
from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager
from workflow_manager.models.workflow_run import WorkflowRun
from workflow_manager.models.analysis_run import AnalysisRun


class CommentManager(OrcaBusBaseManager):
    pass


class Comment(OrcaBusBaseModel):
    orcabus_id = OrcaBusIdField(primary_key=True, prefix='cmt')
    workflow_run = models.ForeignKey(WorkflowRun, related_name="comments", on_delete=models.CASCADE, null=True, blank=True)
    analysis_run = models.ForeignKey(AnalysisRun, related_name="comments", on_delete=models.CASCADE, null=True, blank=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False) # fields for soft delete

    objects = CommentManager()

    def clean(self):
        super().clean()
        has_workflow_run = self.workflow_run_id is not None
        has_analysis_run = self.analysis_run_id is not None
        if has_workflow_run == has_analysis_run:
            raise ValidationError("A comment must be linked to exactly one of workflow_run or analysis_run.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"ID: {self.orcabus_id}, workflow_run: {self.workflow_run}, text: {self.text}"
