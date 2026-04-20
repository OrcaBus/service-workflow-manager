from django.test import TestCase

from workflow_manager.models import Analysis
from workflow_manager.models.analysis import AnalysisStatus
from workflow_manager.models.analysis_context import AnalysisContext, AnalysisContextUseCase
from workflow_manager.models.workflow import Workflow
from workflow_manager.tests.fixtures.sim_analysis import TestData
from workflow_manager.urls.base import api_base


class AnalysisViewSetTestCase(TestCase):
    endpoint = f"/{api_base}analysis"

    def setUp(self):
        TestData().assign_analysis()

    def test_list_returns_200(self):
        response = self.client.get(f"{self.endpoint}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)
        self.assertGreater(len(data["results"]), 0)

    def test_list_with_search(self):
        analysis = Analysis.objects.first()
        response = self.client.get(
            f"{self.endpoint}/",
            {"search": analysis.analysis_name[:4]},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)

    def test_list_with_status_filter(self):
        response = self.client.get(f"{self.endpoint}/", {"status": "ACTIVE"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for item in data["results"]:
            self.assertEqual(item["status"], "ACTIVE")

    def test_list_with_ordering(self):
        response = self.client.get(f"{self.endpoint}/", {"ordering": "-analysis_name"})
        self.assertEqual(response.status_code, 200)

    def test_list_with_invalid_ordering_uses_default(self):
        response = self.client.get(f"{self.endpoint}/", {"ordering": "bogus_field"})
        self.assertEqual(response.status_code, 200)

    def test_retrieve_returns_200(self):
        analysis = Analysis.objects.first()
        if analysis:
            response = self.client.get(f"{self.endpoint}/{analysis.orcabus_id}/")
            self.assertEqual(response.status_code, 200)

    def test_partial_update_description(self):
        analysis = Analysis.objects.first()
        response = self.client.patch(
            f"{self.endpoint}/{analysis.orcabus_id}/",
            data={"description": "Updated description"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        analysis.refresh_from_db()
        self.assertEqual(analysis.description, "Updated description")

    def test_partial_update_status(self):
        analysis = Analysis.objects.filter(status=AnalysisStatus.ACTIVE).first()
        response = self.client.patch(
            f"{self.endpoint}/{analysis.orcabus_id}/",
            data={"status": "INACTIVE"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        analysis.refresh_from_db()
        self.assertEqual(analysis.status, "INACTIVE")

    def test_partial_update_contexts(self):
        analysis = Analysis.objects.first()
        ctx = AnalysisContext.objects.first()
        response = self.client.patch(
            f"{self.endpoint}/{analysis.orcabus_id}/",
            data={"contexts": [ctx.orcabus_id]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_partial_update_workflows(self):
        analysis = Analysis.objects.first()
        wf = Workflow.objects.first()
        response = self.client.patch(
            f"{self.endpoint}/{analysis.orcabus_id}/",
            data={"workflows": [wf.orcabus_id]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
