import uuid

from django.test import TestCase

from workflow_manager.models import Workflow
from workflow_manager.tests.factories import WorkflowRunFactory
from workflow_manager.tests.fixtures.sim_workflow import TestData
from workflow_manager.urls.base import api_base


class StatsViewSetTestCase(TestCase):
    base_endpoint = f"/{api_base}stats"

    def setUp(self):
        TestData().create_primary()
        self.wf = Workflow.objects.first()
        self.wfr_empty = WorkflowRunFactory(
            workflow=self.wf,
            workflow_run_name="EmptyWorkflowRunForStats",
            portal_run_id="8888",
        )

    def test_workflow_run_status_counts_returns_200(self):
        response = self.client.get(f"{self.base_endpoint}/workflow_run/status_counts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            set(data.keys()),
            {"all", "succeeded", "aborted", "failed", "resolved", "deprecated", "ongoing"},
        )
        self.assertGreaterEqual(data["all"], 1)

    def test_analysis_run_status_counts_returns_200(self):
        response = self.client.get(f"{self.base_endpoint}/analysis_run/status_counts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            set(data.keys()),
            {"all", "succeeded", "aborted", "failed", "resolved", "deprecated", "ongoing"},
        )

    def test_workflow_status_counts_returns_200(self):
        response = self.client.get(f"{self.base_endpoint}/workflow/status_counts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("all", data)
        self.assertIn("unvalidated", data)
        self.assertIn("validated", data)
        self.assertIn("deprecated", data)
        self.assertIn("failed", data)
        self.assertGreaterEqual(data["all"], 1)

    def test_analysis_status_counts_returns_200(self):
        response = self.client.get(f"{self.base_endpoint}/analysis/status_counts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("all", data)
        self.assertIn("active", data)
        self.assertIn("inactive", data)

    def test_grouped_workflow_status_counts_returns_200(self):
        response = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            set(data.keys()),
            {"all", "unvalidated", "validated", "deprecated", "failed"},
        )
        self.assertGreaterEqual(data["all"], 1)

    def test_grouped_workflow_status_counts_only_latest_version_per_name(self):
        from workflow_manager.models.workflow import ExecutionEngine, ValidationState

        name = f"wfm_stats_group_{uuid.uuid4().hex[:16]}"
        before = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/").json()

        Workflow.objects.create(
            name=name,
            version="1.0.0",
            code_version="dup-a",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.UNVALIDATED,
        )
        Workflow.objects.create(
            name=name,
            version="10.0.0",
            code_version="dup-b",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )

        after = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/").json()

        self.assertEqual(after["all"], before["all"] + 1)
        self.assertEqual(after["validated"], before["validated"] + 1)
        self.assertEqual(after["unvalidated"], before["unvalidated"])
