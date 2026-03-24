from django.test import TestCase

from workflow_manager.viewsets.workflow_run import WorkflowRunViewSet, _build_keyword_params


class WorkflowRunViewSetHelpersTestCase(TestCase):
    """Unit tests for WorkflowRunViewSet helper functions."""

    def test_build_keyword_params_excludes_custom_params(self):
        from django.http import QueryDict

        qd = QueryDict("start_time=2024-01-01&workflow__orcabus_id=wfl.123&search=foo")
        result = _build_keyword_params(qd)
        self.assertEqual(result, {"workflow__orcabus_id": ["wfl.123"]})

    def test_build_keyword_params_preserves_multiple_values(self):
        from django.http import QueryDict

        qd = QueryDict(mutable=True)
        qd.setlist("workflow__orcabus_id", ["wfl.1", "wfl.2"])
        result = _build_keyword_params(qd)
        self.assertEqual(result["workflow__orcabus_id"], ["wfl.1", "wfl.2"])

    def test_parse_datetime_safe_valid(self):
        result = WorkflowRunViewSet._parse_datetime_safe("2024-01-15T10:30:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

    def test_parse_datetime_safe_invalid_returns_none(self):
        self.assertIsNone(WorkflowRunViewSet._parse_datetime_safe("invalid"))
        self.assertIsNone(WorkflowRunViewSet._parse_datetime_safe(""))
        self.assertIsNone(WorkflowRunViewSet._parse_datetime_safe(None))
        self.assertIsNone(WorkflowRunViewSet._parse_datetime_safe(123))

    def test_validate_ordering_valid(self):
        self.assertEqual(WorkflowRunViewSet._validate_ordering("orcabus_id"), "orcabus_id")
        self.assertEqual(WorkflowRunViewSet._validate_ordering("-orcabus_id"), "-orcabus_id")
        self.assertEqual(WorkflowRunViewSet._validate_ordering("  orcabus_id  "), "orcabus_id")

    def test_validate_ordering_invalid_returns_default(self):
        self.assertEqual(WorkflowRunViewSet._validate_ordering(""), "-orcabus_id")
        self.assertEqual(WorkflowRunViewSet._validate_ordering("invalid_field"), "-orcabus_id")
        self.assertEqual(WorkflowRunViewSet._validate_ordering(None), "-orcabus_id")
