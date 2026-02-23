from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action

from workflow_manager.models import Comment, WorkflowRun
from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager.serializers.comment import CommentSerializer
from .base import NoDeleteViewSet


class BaseCommentViewSet(NoDeleteViewSet):
    """Shared logic for comment CRUD, parameterized by parent model/field."""
    serializer_class = CommentSerializer
    search_fields = Comment.get_base_fields()
    pagination_class = None
    lookup_url_kwarg = "comment_orcabus_id"
    lookup_value_regex = "[^/]+"

    parent_model = None
    parent_field = None
    parent_not_found_msg = "Parent not found."

    def get_queryset(self):
        return Comment.objects.filter(
            **{self.parent_field: self.kwargs["orcabus_id"]},
            is_deleted=False
        )

    def create(self, request, *args, **kwargs):
        parent_orcabus_id = self.kwargs["orcabus_id"]

        try:
            self.parent_model.objects.get(orcabus_id=parent_orcabus_id)
        except self.parent_model.DoesNotExist:
            return Response({"detail": self.parent_not_found_msg}, status=status.HTTP_404_NOT_FOUND)

        if not request.data.get('created_by') or not request.data.get('comment'):
            return Response({"detail": "created_by and comment are required."}, status=status.HTTP_400_BAD_REQUEST)

        mutable_data = request.data.copy()
        mutable_data[self.parent_field] = parent_orcabus_id

        serializer = self.get_serializer(data=mutable_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        if instance.created_by != request.data.get('created_by'):
            raise PermissionDenied("You don't have permission to update this comment.")

        if set(request.data.keys()) - {'comment', 'created_by'}:
            return Response({"detail": "Only the comment field can be updated."},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK, headers=headers)

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=True, methods=["post"], url_path="soft_delete")
    def soft_delete(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.created_by != request.data.get('created_by'):
            raise PermissionDenied("You don't have permission to delete this comment.")

        instance.is_deleted = True
        instance.save()

        return Response({"detail": "Comment successfully marked as deleted."}, status=status.HTTP_204_NO_CONTENT)


class CommentViewSet(BaseCommentViewSet):
    """Comments nested under WorkflowRun."""
    parent_model = WorkflowRun
    parent_field = "workflow_run"
    parent_not_found_msg = "WorkflowRun not found."


class AnalysisRunCommentViewSet(BaseCommentViewSet):
    """Comments nested under AnalysisRun."""
    parent_model = AnalysisRun
    parent_field = "analysis_run"
    parent_not_found_msg = "AnalysisRun not found."
