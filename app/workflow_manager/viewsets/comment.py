from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, mixins
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from workflow_manager.models.workflow_run import WorkflowRun
from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager.models.comment import Comment
from workflow_manager.serializers.comment import (
    CommentSerializer,
    CommentCreateRequestSerializer,
    CommentUpdateRequestSerializer,
)
from .base import PatchOnlyViewSet
from .auth_utils import get_email_from_bearer_authorization


@extend_schema_view(
    create=extend_schema(
        request=CommentCreateRequestSerializer,
        responses={201: CommentSerializer},
        description=(
            "Create a comment (body: text, created_by; optional severity — DEBUG/INFO/WARNING/ERROR, "
            "defaults to INFO; JSON uses camelCase per API settings). "
        ),
    ),
    partial_update=extend_schema(
        request=CommentUpdateRequestSerializer,
        responses={200: CommentSerializer},
        description=(
            "Update comment text and/or severity. At least one of text or severity is required. "
            "Send created_by matching the author, or omit it and use Authorization: Bearer <jwt> "
            "(email claim must match author). Unknown body keys are ignored."
        ),
    ),
    destroy=extend_schema(
        request=None,
        responses={204: None},
        description="Soft-delete. Caller must present Authorization: Bearer <jwt> (RS256); email claim must match comment author (created_by). Signature is not verified here — authenticate at API Gateway.",
    ),
)
class BaseCommentViewSet(PatchOnlyViewSet, mixins.DestroyModelMixin):
    """Shared logic for comment CRUD, parameterized by parent model/field."""
    serializer_class = CommentSerializer
    search_fields = Comment.get_base_fields()
    pagination_class = None
    lookup_url_kwarg = "comment_orcabus_id"
    lookup_value_regex = "[^/]+"
    # PatchOnlyViewSet excludes PUT; we extend it with DELETE for soft-delete.
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options', 'trace']

    parent_model = None
    parent_field = None
    parent_not_found_msg = "Parent Model not found."

    def get_queryset(self):
        return Comment.objects.filter(
            **{self.parent_field: self.kwargs["orcabus_id"]},
            is_deleted=False
        )

    def create(self, request, *args, **kwargs):
        parent_orcabus_id = self.kwargs["orcabus_id"]

        try:
            parent = self.parent_model.objects.get(orcabus_id=parent_orcabus_id)
        except self.parent_model.DoesNotExist:
            return Response({"detail": self.parent_not_found_msg}, status=status.HTTP_404_NOT_FOUND)

        required_fields = {"text", "created_by"}
        provided_fields = set(request.data.keys())

        if required_fields - provided_fields:
            return Response({"detail": "createdBy and text fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        body = CommentCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        create_kwargs = {
            "text": body.validated_data["text"],
            "created_by": body.validated_data["created_by"],
            self.parent_field: parent,
        }
        if "severity" in body.validated_data:
            create_kwargs["severity"] = body.validated_data["severity"]
        instance = Comment.objects.create(**create_kwargs)
        data = CommentSerializer(instance).data
        headers = self.get_success_headers(data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        allowed_fields = {"text", "created_by", "severity"}
        filtered_data = {
            key: value for key, value in request.data.items() if key in allowed_fields
        }

        body = CommentUpdateRequestSerializer(data=filtered_data, partial=partial)
        body.is_valid(raise_exception=True)
        vd = body.validated_data

        if "created_by" in vd:
            actor = vd["created_by"].strip().lower()
        else:
            actor = get_email_from_bearer_authorization(request)
        author = (instance.created_by or "").strip().lower()
        if author != actor:
            raise PermissionDenied("You don't have permission to update this comment.")

        update_fields = ["updated_at"]
        if "text" in vd:
            instance.text = vd["text"]
            update_fields.append("text")
        if "severity" in vd:
            instance.severity = vd["severity"]
            update_fields.append("severity")
        instance.save(update_fields=update_fields)

        data = CommentSerializer(instance).data
        headers = self.get_success_headers(data)
        return Response(data, status=status.HTTP_200_OK, headers=headers)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        email = get_email_from_bearer_authorization(request)
        author = (instance.created_by or "").strip().lower()
        if email != author:
            raise PermissionDenied("You don't have permission to delete this comment.")

        # Soft-delete only flips is_deleted; severity (and text) stay for audit/UI history.
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkflowRunCommentViewSet(BaseCommentViewSet):
    """Comments nested under WorkflowRun."""
    parent_model = WorkflowRun
    parent_field = "workflow_run"
    parent_not_found_msg = "WorkflowRun not found."


class AnalysisRunCommentViewSet(BaseCommentViewSet):
    """Comments nested under AnalysisRun."""
    parent_model = AnalysisRun
    parent_field = "analysis_run"
    parent_not_found_msg = "AnalysisRun not found."
