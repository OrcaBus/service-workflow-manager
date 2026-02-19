from django.db import models

from workflow_manager.fields import OrcaBusIdField
from workflow_manager.models.base import OrcaBusBaseModel, OrcaBusBaseManager
from workflow_manager.models.workflow_run import WorkflowRun
from workflow_manager.models.analysis_run import AnalysisRun


class CommentManager(OrcaBusBaseManager):
    pass


class Comment(OrcaBusBaseModel):
    orcabus_id = OrcaBusIdField(primary_key=True, prefix='cmt')
    workflow_run = models.ForeignKey(WorkflowRun, related_name="comments", on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False) # fields for soft delete

    objects = CommentManager()

    def __str__(self):
        return f"ID: {self.orcabus_id}, workflow_run: {self.workflow_run}, text: {self.text}"
