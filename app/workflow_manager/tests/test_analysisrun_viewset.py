from django.test import TestCase

from workflow_manager.models import AnalysisRun
from workflow_manager.tests.fixtures.sim_analysis import TestData
from workflow_manager.urls.base import api_base


class AnalysisRunViewSetTestCase(TestCase):
    """Tests for AnalysisRunViewSet list and retrieve."""

    endpoint = f"/{api_base}analysisrun"

    def setUp(self):
        TestData().assign_analysis()

    def test_list_returns_200(self):
        response = self.client.get(f"{self.endpoint}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)

    def test_list_with_keyword_params(self):
        ar = AnalysisRun.objects.filter(analysis__isnull=False).first()
        if ar:
            response = self.client.get(
                f"{self.endpoint}/",
                {"analysis__orcabus_id": ar.analysis.orcabus_id},
            )
            self.assertEqual(response.status_code, 200)

    def test_retrieve_returns_200(self):
        ar = AnalysisRun.objects.first()
        if ar:
            response = self.client.get(f"{self.endpoint}/{ar.orcabus_id}/")
            self.assertEqual(response.status_code, 200)


class AnalysisRunCommentViewSetTestCase(TestCase):
    endpoint = f"/{api_base}analysisrun"

    def setUp(self):
        TestData().assign_analysis()
        self.analysis_run = AnalysisRun.objects.first()

    def test_create_comment_parent_not_found(self):
        url = f"{self.endpoint}/anr.nonexistent123/comment/"
        response = self.client.post(
            url,
            data={"text": "x", "created_by": "u"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("AnalysisRun not found", response.json()["detail"])
