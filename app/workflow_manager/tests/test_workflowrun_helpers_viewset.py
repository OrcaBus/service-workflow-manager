from django.test import TestCase

from workflow_manager.viewsets.utils import build_keyword_params, parse_datetime_safe, validate_ordering
from workflow_manager.viewsets.workflow_run import ALLOWED_ORDER_FIELDS


class WorkflowRunViewSetHelpersTestCase(TestCase):
    """Unit tests for workflow run query helpers."""

    def test_build_keyword_params_excludes_custom_params(self):
        from django.http import QueryDict

        qd = QueryDict("start_time=2024-01-01&workflow__orcabus_id=wfl.123&search=foo")
        result = build_keyword_params(qd)
        self.assertEqual(result, {"workflow__orcabus_id": ["wfl.123"]})

    def test_build_keyword_params_preserves_multiple_values(self):
        from django.http import QueryDict

        qd = QueryDict(mutable=True)
        qd.setlist("workflow__orcabus_id", ["wfl.1", "wfl.2"])
        result = build_keyword_params(qd)
        self.assertEqual(result["workflow__orcabus_id"], ["wfl.1", "wfl.2"])

    def test_parse_datetime_safe_valid(self):
        result = parse_datetime_safe("2024-01-15T10:30:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

    def test_parse_datetime_safe_invalid_returns_none(self):
        self.assertIsNone(parse_datetime_safe("invalid"))
        self.assertIsNone(parse_datetime_safe(""))
        self.assertIsNone(parse_datetime_safe(None))
        self.assertIsNone(parse_datetime_safe(123))

    def test_validate_ordering_valid(self):
        self.assertEqual(validate_ordering("orcabus_id", ALLOWED_ORDER_FIELDS), "orcabus_id")
        self.assertEqual(validate_ordering("-orcabus_id", ALLOWED_ORDER_FIELDS), "-orcabus_id")
        self.assertEqual(validate_ordering("  orcabus_id  ", ALLOWED_ORDER_FIELDS), "orcabus_id")

    def test_validate_ordering_invalid_returns_none(self):
        self.assertIsNone(validate_ordering("", ALLOWED_ORDER_FIELDS))
        self.assertIsNone(validate_ordering("invalid_field", ALLOWED_ORDER_FIELDS))
        self.assertIsNone(validate_ordering(None, ALLOWED_ORDER_FIELDS))
