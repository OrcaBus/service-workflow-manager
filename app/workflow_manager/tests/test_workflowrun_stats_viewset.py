from datetime import datetime, timedelta

from django.test import TestCase
from django.utils.timezone import is_aware, make_aware

from workflow_manager.models import Workflow, WorkflowRun
from workflow_manager.tests.factories import WorkflowRunFactory
from workflow_manager.tests.fixtures.sim_workflow import TestData
from workflow_manager.urls.base import api_base


class WorkflowRunStatsViewSetTestCase(TestCase):
    endpoint = f"/{api_base}workflowrun/stats"

    def setUp(self):
        TestData().create_primary()
        self.wf = Workflow.objects.first()
        self.wfr_empty = WorkflowRunFactory(
            workflow=self.wf,
            workflow_run_name="EmptyWorkflowRunForStats",
            portal_run_id="8888",
        )

    def test_list_stats_returns_200(self):
        response = self.client.get(f"{self.endpoint}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

    def test_list_all_action_returns_200(self):
        response = self.client.get(f"{self.endpoint}/list_all/")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_count_by_status_returns_200_and_buckets(self):
        response = self.client.get(f"{self.endpoint}/count_by_status/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            set(data.keys()),
            {"all", "succeeded", "aborted", "failed", "resolved", "deprecated", "ongoing"},
        )

    def test_list_with_status_filter_latest_state(self):
        response = self.client.get(f"{self.endpoint}/", {"status": "FAILED"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data), 1)
        for item in data:
            current_state = item.get("currentState", item.get("current_state"))
            self.assertIsNotNone(current_state)
            self.assertEqual(current_state["status"], "FAILED")

    def test_list_with_is_ongoing_true_returns_200(self):
        response = self.client.get(f"{self.endpoint}/", {"is_ongoing": "true"})
        self.assertEqual(response.status_code, 200)

    def test_list_with_order_by_timestamp(self):
        response = self.client.get(f"{self.endpoint}/", {"order_by": "timestamp"})
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_list_with_order_by_minus_timestamp(self):
        response = self.client.get(f"{self.endpoint}/", {"order_by": "-timestamp"})
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_list_with_start_and_end_time_range(self):
        start = make_aware(datetime.now() - timedelta(days=1))
        end = make_aware(datetime.now() + timedelta(days=1))
        response = self.client.get(
            f"{self.endpoint}/",
            {"start_time": start.isoformat(), "end_time": end.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_list_with_search_returns_200(self):
        wfr = WorkflowRun.objects.first()
        response = self.client.get(
            f"{self.endpoint}/",
            {"search": (wfr.workflow_run_name or "Test")[:10]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_parse_datetime_safe_various_inputs(self):
        from workflow_manager.viewsets.workflow_run_stats import WorkflowRunStatsViewSet

        self.assertIsNone(WorkflowRunStatsViewSet._parse_datetime_safe(""))
        self.assertIsNone(WorkflowRunStatsViewSet._parse_datetime_safe(None))
        self.assertIsNone(WorkflowRunStatsViewSet._parse_datetime_safe(123))

        dt = WorkflowRunStatsViewSet._parse_datetime_safe("2024-01-15T10:30:00")
        self.assertIsNotNone(dt)
        self.assertTrue(is_aware(dt))

        aware_dt = WorkflowRunStatsViewSet._parse_datetime_safe("2024-01-15T10:30:00+10:00")
        self.assertIsNotNone(aware_dt)
        self.assertTrue(is_aware(aware_dt))
        self.assertEqual(aware_dt.utcoffset(), timedelta(hours=10))
