import logging
import operator
from functools import reduce
from typing import List

from django.core.exceptions import FieldError
from django.db import models
from django.db.models import Q, ManyToManyField, ForeignKey, ForeignObject, OneToOneField, ForeignObjectRel, \
    ManyToOneRel, ManyToManyRel, OneToOneRel, QuerySet
from rest_framework.settings import api_settings
from workflow_manager.pagination import PaginationConstant

logger = logging.getLogger(__name__)


class OrcaBusBaseManager(models.Manager):

    def get_by_keyword(self, qs=None, **kwargs) -> QuerySet:
        if qs is None:
            qs = super().get_queryset()
        return self.get_model_fields_query(qs, **kwargs)

    @staticmethod
    def reduce_multi_values_qor(key: str, values):
        """
        Build Q objects for OR filter across multiple values.
        Handles: single value, list of values, and comma-separated string (e.g. id1,id2,id3).
        """
        if values is None:
            return Q()
        if not isinstance(values, list):
            values = [values]
        # Expand comma-separated strings (e.g. "id1,id2,id3" -> ["id1", "id2", "id3"])
        expanded = []
        for v in values:
            if isinstance(v, str) and "," in v:
                expanded.extend(x.strip() for x in v.split(",") if x.strip())
            else:
                expanded.append(v)
        values = expanded
        if not values:
            return Q()
        return reduce(
            # Apparently the `get_prep_value` from the custom fields.py is not called prior hitting the Db but,
            # the regular `__exact` still execute that function.
            operator.or_, (Q(**{"%s__exact" % key: value}) for value in values)
        )

    def get_model_fields_query(self, qs: QuerySet, **kwargs) -> QuerySet:

        def exclude_params(params):
            for param in params:
                kwargs.pop(param) if param in kwargs.keys() else None

        exclude_params(
            [
                api_settings.SEARCH_PARAM,
                api_settings.ORDERING_PARAM,
                PaginationConstant.PAGE,
                PaginationConstant.ROWS_PER_PAGE,
                "sortCol",
                "sortAsc",
            ]
        )

        query_string = None

        for key, values in kwargs.items():
            each_query = self.reduce_multi_values_qor(key, values)
            if query_string:
                query_string = query_string & each_query
            else:
                query_string = each_query

        try:
            if query_string:
                qs = qs.filter(query_string)
        except FieldError as e:
            logger.debug(e)
            qs = qs.none()

        return qs


class OrcaBusBaseModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()  # make sure we are validating the inputs (especially the OrcaBus ID)
        super(OrcaBusBaseModel, self).save(*args, **kwargs)

        # Reload the object from the database to ensure custom fields like OrcaBusIdField
        # invoke the `from_db_value` method (which provides the annotation) after saving.
        self.refresh_from_db()

    @classmethod
    def get_fields(cls):
        return [f.name for f in cls._meta.get_fields()]

    @classmethod
    def get_base_fields(cls):
        base_fields = set()
        for f in cls._meta.get_fields():
            if isinstance(f, (ForeignKey, ForeignObject, OneToOneField, ManyToManyField,
                              ForeignObjectRel, ManyToOneRel, ManyToManyRel, OneToOneRel,)):
                continue
            base_fields.add(f.name)
        return list(base_fields)
