from abc import ABC

from rest_framework import filters, mixins
from rest_framework.viewsets import ReadOnlyModelViewSet, GenericViewSet

from workflow_manager.pagination import StandardResultsSetPagination


class BaseViewSet(ReadOnlyModelViewSet, ABC):
    lookup_value_regex = "[^/]+"  # This is to allow for special characters in the URL
    ordering_fields = "__all__"
    ordering = ["-orcabus_id"]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]


class PatchOnlyViewSet(mixins.CreateModelMixin,
                       mixins.RetrieveModelMixin,
                       mixins.UpdateModelMixin,
                       mixins.ListModelMixin,
                       GenericViewSet, ABC):
    lookup_value_regex = "[^/]+"  # This is to allow for special characters in the URL
    ordering_fields = "__all__"
    ordering = ["-orcabus_id"]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    http_method_names = ['get', 'post', 'patch', 'head', 'options', 'trace']  # no PUT method and PATCH only for update
