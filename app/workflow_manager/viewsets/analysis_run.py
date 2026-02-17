from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager.serializers.base import OrcabusIdListUtils
from workflow_manager.serializers.analysis_run import (
    AnalysisRunDetailSerializer,
    AnalysisRunSerializer,
    AnalysisRunListParamSerializer,
    WritableAnalysisRunSerializer,
)
from .base import NoDeleteViewSet


class AnalysisRunViewSet(NoDeleteViewSet):
    serializer_class = AnalysisRunDetailSerializer  # use detailed for retrieve
    search_fields = AnalysisRun.get_base_fields()
    queryset = AnalysisRun.objects.prefetch_related(
        "libraries", "contexts", "readsets", "states"
    ).select_related("analysis").all()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return WritableAnalysisRunSerializer
        if self.action == "list":
            return AnalysisRunSerializer
        return AnalysisRunDetailSerializer

    def _get_output_serializer(self, instance):
        """Use read serializer for response output (nested objects, proper M2M handling)."""
        instance = AnalysisRun.objects.prefetch_related(
            "libraries", "contexts", "readsets", "states"
        ).select_related("analysis").get(pk=instance.pk)
        return AnalysisRunDetailSerializer(instance)

    @extend_schema(parameters=[
        AnalysisRunListParamSerializer,
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=WritableAnalysisRunSerializer,
        responses={
            status.HTTP_201_CREATED: AnalysisRunDetailSerializer,
        },
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output_serializer = self._get_output_serializer(instance)
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def _filter_empty_for_partial(self, data):
        """For PATCH: omit empty values so they are not updated."""
        if not data:
            return data
        filtered = {}
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, list):
                normalized = OrcabusIdListUtils.normalize(value)
                if not normalized:
                    continue
                value = normalized
            filtered[key] = value
        return filtered

    @extend_schema(
        request=WritableAnalysisRunSerializer,
        responses={
            status.HTTP_200_OK: AnalysisRunDetailSerializer,
        },
    )
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        data = self._filter_empty_for_partial(request.data) if partial else request.data
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output_serializer = self._get_output_serializer(instance)
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=WritableAnalysisRunSerializer,
        responses={
            status.HTTP_200_OK: AnalysisRunDetailSerializer,
        },
    )
    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def get_queryset(self):
        query_params = self.request.query_params.copy()
        return AnalysisRun.objects.get_by_keyword(self.queryset, **query_params)
