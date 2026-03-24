from datetime import datetime, timedelta
from unittest.mock import MagicMock

from django.test import TestCase
from django.utils.timezone import make_aware

from workflow_manager.models import State, Workflow, WorkflowRun
from workflow_manager.tests.factories import StateFactory, WorkflowRunFactory
from workflow_manager.tests.fixtures.sim_workflow import TestData
from workflow_manager.urls.base import api_base


class StateViewSetTestCase(TestCase):
    endpoint = f"/{api_base}workflowrun"

    def setUp(self):
        TestData().create_primary()
        self.wf = Workflow.objects.first()
        self.wfr_failed = WorkflowRun.objects.get(portal_run_id="1234")
        self.wfr_succeeded = WorkflowRun.objects.get(portal_run_id="1235")
        self.wfr_empty = WorkflowRunFactory(
            workflow=self.wf,
            workflow_run_name="EmptyStateWorkflowRun",
            portal_run_id="9999",
        )

        self.state_ready = State.objects.get(workflow_run=self.wfr_failed, status="READY")

    def test_list_states_returns_200(self):
        url = f"{self.endpoint}/{self.wfr_failed.orcabus_id}/state/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

    def test_get_states_transition_validation_map_returns_200(self):
        url = f"{self.endpoint}/{self.wfr_failed.orcabus_id}/state/get_states_transition_validation_map/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("RESOLVED", data)
        self.assertIn("DEPRECATED", data)

    def test_create_state_requires_status_and_comment_fields(self):
        url = f"{self.endpoint}/{self.wfr_failed.orcabus_id}/state/"
        response = self.client.post(url, data={}, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("status and comment fields are required", response.json()["detail"])

    def test_create_state_valid_transition_failed_to_resolved(self):
        url = f"{self.endpoint}/{self.wfr_failed.orcabus_id}/state/"
        response = self.client.post(
            url,
            data={"status": "RESOLVED", "comment": "resolved ok"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "RESOLVED")
        self.assertEqual(data["comment"], "resolved ok")

    def test_create_state_rejects_invalid_transition_failed_to_deprecated(self):
        url = f"{self.endpoint}/{self.wfr_failed.orcabus_id}/state/"
        response = self.client.post(
            url,
            data={"status": "DEPRECATED", "comment": "should fail"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid state request", response.json()["detail"])

    def test_create_state_rejects_non_deprecated_when_no_latest_state(self):
        url = f"{self.endpoint}/{self.wfr_empty.orcabus_id}/state/"
        response = self.client.post(
            url,
            data={"status": "READY", "comment": "no latest state yet"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Only DEPRECATED is allowed when there are no states",
            response.json()["detail"],
        )

    def test_create_state_allows_deprecated_when_no_latest_state(self):
        url = f"{self.endpoint}/{self.wfr_empty.orcabus_id}/state/"
        response = self.client.post(
            url,
            data={"status": "DEPRECATED", "comment": "deprecated first state"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "DEPRECATED")

    def test_update_state_comment_requires_comment_field(self):
        url = f"{self.endpoint}/{self.wfr_failed.orcabus_id}/state/{self.state_ready.orcabus_id}/"
        response = self.client.patch(url, data={}, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("comment field is required", response.json()["detail"])

    def test_update_state_comment_rejects_states_outside_validation_map(self):
        url = f"{self.endpoint}/{self.wfr_failed.orcabus_id}/state/{self.state_ready.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"comment": "x"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid state status to update comment.", response.json()["detail"])

    def test_update_state_comment_success(self):
        state_deprecated = StateFactory(
            workflow_run=self.wfr_failed,
            status="DEPRECATED",
            timestamp=make_aware(datetime.now() + timedelta(hours=10)),
            comment="old",
        )
        url = f"{self.endpoint}/{self.wfr_failed.orcabus_id}/state/{state_deprecated.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"comment": "updated"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["comment"], "updated")

    def test_is_valid_next_state_current_status_none_only_allows_deprecated(self):
        from workflow_manager.viewsets.state import StateViewSet

        viewset = StateViewSet()
        self.assertTrue(viewset.is_valid_next_state(None, "DEPRECATED"))
        self.assertFalse(viewset.is_valid_next_state(None, "RESOLVED"))

    def test_is_valid_next_state_allowed_states_dict_branch(self):
        from workflow_manager.viewsets.state import StateViewSet

        viewset = StateViewSet()
        viewset.states_transition_validation_map = {"X": {"allowed_states": ["A", "B"]}}
        self.assertTrue(viewset.is_valid_next_state("a", "X"))
        self.assertFalse(viewset.is_valid_next_state("C", "X"))

    def test_is_valid_next_state_dict_unknown_shape_falls_back_to_false(self):
        from workflow_manager.viewsets.state import StateViewSet

        viewset = StateViewSet()
        viewset.states_transition_validation_map = {"X": {"other": ["A"]}}
        self.assertFalse(viewset.is_valid_next_state("A", "X"))

    def test_is_valid_next_state_unknown_request_status_returns_false(self):
        from workflow_manager.viewsets.state import StateViewSet

        viewset = StateViewSet()
        self.assertFalse(viewset.is_valid_next_state("READY", "NOT_IN_MAP"))

    def test_update_prefetched_objects_cache_invalidation_runs(self):
        """
        Cover the `_prefetched_objects_cache` invalidation block in `update()`.
        The HTTP path doesn't naturally trigger that block because the view's
        queryset doesn't prefetch related objects.
        """
        from unittest.mock import MagicMock
        from workflow_manager.viewsets.state import StateViewSet

        viewset = StateViewSet()
        request = MagicMock()
        request.data = {"comment": "new"}
        viewset.get_success_headers = MagicMock(return_value={})

        state_deprecated = StateFactory(
            workflow_run=self.wfr_failed,
            status="DEPRECATED",
            timestamp=make_aware(datetime.now() + timedelta(hours=20)),
            comment="old",
        )
        state_deprecated._prefetched_objects_cache = {"prefetched": True}

        viewset.get_object = MagicMock(return_value=state_deprecated)
        response = viewset.update(request, partial=True)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(state_deprecated._prefetched_objects_cache, {})
        state_deprecated.refresh_from_db()
        self.assertEqual(state_deprecated.comment, "new")
