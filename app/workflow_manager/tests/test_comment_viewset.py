from unittest.mock import patch

from django.test import TestCase

from workflow_manager.models import Comment, WorkflowRun
from workflow_manager.tests.fixtures.sim_workflow import TestData
from workflow_manager.urls.base import api_base


class CommentViewSetTestCase(TestCase):
    endpoint = f"/{api_base}workflowrun"

    def setUp(self):
        TestData().create_primary()
        self.wfr = WorkflowRun.objects.first()

    def test_list_comments_empty(self):
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_create_comment_success(self):
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/"
        response = self.client.post(
            url,
            data={"text": "New comment", "created_by": "tester"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["text"], "New comment")
        self.assertEqual(data.get("createdBy", data.get("created_by")), "tester")
        self.assertEqual(data.get("severity"), "INFO")

    def test_create_comment_with_optional_severity(self):
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/"
        response = self.client.post(
            url,
            data={
                "text": "Error comment",
                "created_by": "tester",
                "severity": "ERROR",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["text"], "Error comment")
        self.assertEqual(data.get("severity"), "ERROR")

    def test_create_comment_parent_not_found(self):
        url = f"{self.endpoint}/wfr.nonexistent123/comment/"
        response = self.client.post(
            url,
            data={"text": "x", "created_by": "u"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("WorkflowRun not found", response.json()["detail"])

    def test_create_comment_missing_required_fields(self):
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/"
        response = self.client.post(
            url,
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("createdBy and text fields are required", response.json()["detail"])

    def test_update_comment_success(self):
        c = Comment.objects.create(workflow_run=self.wfr, text="original", created_by="tester")
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"text": "updated", "created_by": "tester"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.text, "updated")

    def test_update_comment_permission_denied(self):
        c = Comment.objects.create(workflow_run=self.wfr, text="original", created_by="creator")
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"text": "hacked", "created_by": "other_user"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_update_comment_extra_fields_ignored(self):
        c = Comment.objects.create(workflow_run=self.wfr, text="original", created_by="tester")
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"text": "ok", "created_by": "tester", "extra_field": "x"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.text, "ok")

    def test_update_comment_severity_updated(self):
        c = Comment.objects.create(
            workflow_run=self.wfr,
            text="original",
            created_by="tester",
            severity="WARNING",
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={
                "text": "updated",
                "created_by": "tester",
                "severity": "ERROR",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.severity, "ERROR")
        self.assertEqual(c.text, "updated")

    def test_update_comment_severity_only(self):
        c = Comment.objects.create(
            workflow_run=self.wfr,
            text="unchanged",
            created_by="tester",
            severity="INFO",
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"severity": "WARNING", "created_by": "tester"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.severity, "WARNING")
        self.assertEqual(c.text, "unchanged")

    def test_update_comment_requires_text_or_severity(self):
        c = Comment.objects.create(workflow_run=self.wfr, text="x", created_by="tester")
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"created_by": "tester"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch(
        "workflow_manager.viewsets.utils.decode_rs256_jwt_payload_without_verification",
        return_value={"email": "tester"},
    )
    def test_update_comment_uses_bearer_when_created_by_omitted(self, _mock_decode):
        c = Comment.objects.create(workflow_run=self.wfr, text="original", created_by="tester")
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"text": "via jwt"},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer fake.jwt.token",
        )
        self.assertEqual(response.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.text, "via jwt")

    def test_update_comment_requires_bearer_when_created_by_omitted(self):
        c = Comment.objects.create(workflow_run=self.wfr, text="original", created_by="tester")
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"text": "no auth"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @patch(
        "workflow_manager.viewsets.utils.decode_rs256_jwt_payload_without_verification",
        return_value={"email": "tester"},
    )
    def test_soft_delete_success(self, _mock_decode):
        c = Comment.objects.create(
            workflow_run=self.wfr,
            text="to delete",
            created_by="tester",
            severity="ERROR",
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.delete(
            url,
            HTTP_AUTHORIZATION="Bearer fake.jwt.token",
        )
        self.assertEqual(response.status_code, 204)
        c.refresh_from_db()
        self.assertTrue(c.is_deleted)
        self.assertEqual(c.severity, "ERROR")

    @patch(
        "workflow_manager.viewsets.utils.decode_rs256_jwt_payload_without_verification",
        return_value={"email": "other_user"},
    )
    def test_soft_delete_permission_denied(self, _mock_decode):
        c = Comment.objects.create(workflow_run=self.wfr, text="x", created_by="creator")
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.delete(
            url,
            HTTP_AUTHORIZATION="Bearer fake.jwt.token",
        )
        self.assertEqual(response.status_code, 403)

    def test_soft_delete_requires_bearer_token(self):
        c = Comment.objects.create(workflow_run=self.wfr, text="x", created_by="tester")
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 401)
