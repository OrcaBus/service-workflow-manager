from django.test import TestCase

from workflow_manager.models import WorkflowRun
from workflow_manager.tests.fixtures.sim_workflow import TestData
from workflow_manager.urls.base import api_base


class WorkflowRunViewSetTestCase(TestCase):
    """Tests for WorkflowRunViewSet list, filters, ongoing, and unresolved actions."""

    endpoint = f"/{api_base}workflowrun"

    def setUp(self):
        TestData().create_primary()

    def test_list_returns_200(self):
        response = self.client.get(f"{self.endpoint}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)
        self.assertGreater(len(data["results"]), 0)

    def test_list_with_start_time_and_end_time(self):
        from datetime import datetime, timedelta
        from django.utils.timezone import make_aware

        start = make_aware(datetime.now() + timedelta(hours=1))
        end = make_aware(datetime.now() + timedelta(hours=3))
        response = self.client.get(
            f"{self.endpoint}/",
            {"start_time": start.isoformat(), "end_time": end.isoformat()},
        )
        self.assertEqual(response.status_code, 200)

    def test_list_with_is_ongoing_true(self):
        response = self.client.get(f"{self.endpoint}/", {"is_ongoing": "true"})
        self.assertEqual(response.status_code, 200)

    def test_list_with_status_filter(self):
        response = self.client.get(f"{self.endpoint}/", {"status": "FAILED"})
        self.assertEqual(response.status_code, 200)

    def test_list_with_order_by_timestamp(self):
        response = self.client.get(f"{self.endpoint}/", {"order_by": "timestamp"})
        self.assertEqual(response.status_code, 200)

    def test_list_with_order_by_minus_timestamp(self):
        response = self.client.get(f"{self.endpoint}/", {"order_by": "-timestamp"})
        self.assertEqual(response.status_code, 200)

    def test_list_with_search(self):
        wfr = WorkflowRun.objects.first()
        response = self.client.get(
            f"{self.endpoint}/",
            {"search": wfr.workflow_run_name[:10] if wfr.workflow_run_name else "Test"},
        )
        self.assertEqual(response.status_code, 200)

    def test_list_with_keyword_params(self):
        wfr = WorkflowRun.objects.first()
        response = self.client.get(f"{self.endpoint}/", {"workflow__orcabus_id": wfr.workflow.orcabus_id})
        self.assertEqual(response.status_code, 200)

    def test_ongoing_action_returns_200(self):
        response = self.client.get(f"{self.endpoint}/ongoing/")
        self.assertEqual(response.status_code, 200)

    def test_ongoing_with_ordering(self):
        response = self.client.get(
            f"{self.endpoint}/ongoing/",
            {"ordering": "orcabus_id"},
        )
        self.assertEqual(response.status_code, 200)

    def test_ongoing_with_keyword_and_status(self):
        wfr = WorkflowRun.objects.first()
        response = self.client.get(
            f"{self.endpoint}/ongoing/",
            {"workflow__orcabus_id": wfr.workflow.orcabus_id, "status": "RUNNING"},
        )
        self.assertEqual(response.status_code, 200)

    def test_unresolved_action_returns_200(self):
        response = self.client.get(f"{self.endpoint}/unresolved/")
        self.assertEqual(response.status_code, 200)

    def test_unresolved_with_ordering(self):
        response = self.client.get(
            f"{self.endpoint}/unresolved/",
            {"ordering": "-orcabus_id"},
        )
        self.assertEqual(response.status_code, 200)

    def test_retrieve_returns_200(self):
        wfr = WorkflowRun.objects.first()
        response = self.client.get(f"{self.endpoint}/{wfr.orcabus_id}/")
        self.assertEqual(response.status_code, 200)
