import logging

from django.test import TestCase

from workflow_manager.models import Workflow
from workflow_manager.tests.factories import WorkflowFactory
from workflow_manager.urls.base import api_base

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class WorkflowViewSetTestCase(TestCase):
    endpoint = f"/{api_base}workflow"

    def setUp(self):
        WorkflowFactory.create_batch(size=1)

    def test_get_api(self):
        response = self.client.get(f"{self.endpoint}/")
        logger.info(response.content)
        self.assertEqual(response.status_code, 200, "Ok status response is expected")

    def test_list_groups_by_name_returns_highest_version_with_history(self):
        from workflow_manager.models.workflow import ExecutionEngine, ValidationState

        Workflow.objects.create(
            name="sash",
            version="0.6.0",
            code_version="a",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )
        Workflow.objects.create(
            name="sash",
            version="0.7.0",
            code_version="b",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )
        Workflow.objects.create(
            name="sash",
            version="0.6.1",
            code_version="c",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )
        Workflow.objects.create(
            name="other",
            version="1.0.0",
            code_version="d",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )

        response = self.client.get(f"{self.endpoint}/grouped/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data.get("results", data) if "results" in data else data

        names = [r["name"] for r in results]
        self.assertIn("sash", names)
        self.assertIn("other", names)

        sash_result = next(r for r in results if r["name"] == "sash")
        self.assertEqual(sash_result["version"], "0.7.0", "sash should return highest version")
        self.assertIn("history", sash_result)
        self.assertEqual(len(sash_result["history"]), 3, "sash history should have 3 version records")

    def test_list_groups_by_name_case_insensitive(self):
        from workflow_manager.models.workflow import ExecutionEngine, ValidationState

        Workflow.objects.create(
            name="Sash",
            version="0.6.0",
            code_version="a",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )
        Workflow.objects.create(
            name="sash",
            version="0.7.0",
            code_version="b",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )
        Workflow.objects.create(
            name="SASH",
            version="0.5.0",
            code_version="c",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )

        response = self.client.get(f"{self.endpoint}/grouped/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data.get("results", data)

        sash_results = [r for r in results if r["name"].lower() == "sash"]
        self.assertEqual(len(sash_results), 1, "Sash/sash/SASH should merge into one group")
        self.assertEqual(sash_results[0]["version"], "0.7.0", "Highest version across case variants")
        self.assertEqual(len(sash_results[0]["history"]), 3, "History should include all 3 case variants")
