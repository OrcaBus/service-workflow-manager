import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.db import DatabaseError
from django.utils.timezone import make_aware

from workflow_manager.models import (
    State,
    Workflow,
    WorkflowRun,
)
from workflow_manager.tests.factories import StateFactory, WorkflowRunFactory
from workflow_manager.tests.fixtures.sim_workflow import TestData
from workflow_manager.urls.base import api_base


class StateViewSetTestCase(TestCase):
    endpoint = f"/{api_base}workflowrun"
    deprecate_endpoint = f"/{api_base}workflowrun/state/deprecate/"
    resolve_endpoint = f"/{api_base}workflowrun/state/resolve/"
    cancel_endpoint = f"/{api_base}workflowrun/state/cancel/"

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

        self.state_ready = State.objects.get(
            workflow_run=self.wfr_failed, status="READY"
        )

    def test_list_states_returns_200(self):
        url = f"{self.endpoint}/{self.wfr_failed.orcabus_id}/state/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

    def test_get_states_transition_validation_map_returns_200(self):
        url = f"{self.endpoint}/state/get_states_transition_validation_map/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("RESOLVED", data)
        self.assertIn("DEPRECATED", data)
        self.assertIn("CANCELLED", data["CANCELLED"]["excludedStates"])

    def test_state_transition_openapi_documents_all_response_shapes(self):
        response = self.client.get(
            "/schema/openapi.json",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)

        expected_statuses = {"201", "207", "400", "500", "502"}
        transition_paths = (
            self.deprecate_endpoint,
            self.resolve_endpoint,
            self.cancel_endpoint,
        )
        for transition_path in transition_paths:
            with self.subTest(transition_path=transition_path):
                responses = schema["paths"][transition_path]["post"]["responses"]
                self.assertTrue(expected_statuses.issubset(responses))
                self.assertEqual(
                    responses["400"]["content"]["application/json"]["schema"],
                    {"$ref": "#/components/schemas/StateTransitionBadRequest"},
                )

        bad_request_variants = schema["components"]["schemas"][
            "StateTransitionBadRequest"
        ]["oneOf"]
        self.assertCountEqual(
            [variant["$ref"] for variant in bad_request_variants],
            [
                "#/components/schemas/StateTransitionValidationError",
                "#/components/schemas/StateTransitionResponse",
            ],
        )

    def test_nested_states_transition_validation_map_route_is_not_available(self):
        url = f"{self.endpoint}/{self.wfr_failed.orcabus_id}/state/get_states_transition_validation_map/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_generic_state_endpoint_no_longer_accepts_post(self):
        url = f"{self.endpoint}/{self.wfr_failed.orcabus_id}/state/"
        response = self.client.post(
            url,
            data={"status": "RESOLVED", "comment": "old endpoint"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 405)

    def test_resolve_requires_comment(self):
        response = self.client.post(
            self.resolve_endpoint,
            data={"workflowrunOrcabusIds": [self.wfr_failed.orcabus_id]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("comment", response.json())

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_resolve_transitions_failed_workflow_run(self, mock_emit_wrsc):
        response = self.client.post(
            self.resolve_endpoint,
            data={
                "workflowrunOrcabusIds": [self.wfr_failed.orcabus_id],
                "comment": "resolved ok",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["createdCount"], 1)
        self.assertEqual(data["failedCount"], 0)
        self.assertEqual(data["workflowrunOrcabusIds"], [self.wfr_failed.orcabus_id])
        self.assertTrue(
            State.objects.filter(
                workflow_run=self.wfr_failed,
                status="RESOLVED",
                comment="resolved ok",
            ).exists()
        )
        mock_emit_wrsc.assert_called_once()
        wrsc_event = mock_emit_wrsc.call_args.args[0]
        self.assertEqual(wrsc_event["status"], "RESOLVED")
        self.assertEqual(wrsc_event["orcabusId"], self.wfr_failed.orcabus_id)
        self.assertEqual(wrsc_event["workflow"]["orcabusId"], self.wf.orcabus_id)
        self.assertNotIn("payload", wrsc_event)

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_deprecate_transitions_succeeded_workflow_run(self, mock_emit_wrsc):
        response = self.client.post(
            self.deprecate_endpoint,
            data={
                "workflowrunOrcabusIds": [self.wfr_succeeded.orcabus_id],
                "comment": "no longer needed",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["createdCount"], 1)
        self.assertEqual(data["workflowrunOrcabusIds"], [self.wfr_succeeded.orcabus_id])
        self.assertTrue(
            State.objects.filter(
                workflow_run=self.wfr_succeeded,
                status="DEPRECATED",
                comment="no longer needed",
            ).exists()
        )
        mock_emit_wrsc.assert_called_once()
        self.assertEqual(mock_emit_wrsc.call_args.args[0]["status"], "DEPRECATED")

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_deprecate_rejects_failed_workflow_run(self, mock_emit_wrsc):
        response = self.client.post(
            self.deprecate_endpoint,
            data={
                "workflowrunOrcabusIds": [self.wfr_failed.orcabus_id],
                "comment": "should fail",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["createdCount"], 0)
        self.assertEqual(data["failedCount"], 1)
        self.assertEqual(data["failures"][0]["reason"], "INVALID_TRANSITION")
        mock_emit_wrsc.assert_not_called()

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_deprecate_preserves_no_source_state_behavior(self, mock_emit_wrsc):
        response = self.client.post(
            self.deprecate_endpoint,
            data={
                "workflowrunOrcabusIds": [self.wfr_empty.orcabus_id],
                "comment": "deprecated first state",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["createdCount"], 1)
        self.assertTrue(
            State.objects.filter(
                workflow_run=self.wfr_empty,
                status="DEPRECATED",
                comment="deprecated first state",
            ).exists()
        )
        mock_emit_wrsc.assert_called_once()

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_cancel_preserves_existing_allowed_source_states(self, mock_emit_wrsc):
        source_statuses = [
            "DRAFT",
            "READY",
            "SUBMITTED",
            "RUNNABLE",
            "STARTING",
            "RUNNING",
            "PAUSED",
        ]
        workflow_runs = []
        for index, source_status in enumerate(source_statuses):
            workflow_run = WorkflowRunFactory(
                workflow=self.wf,
                portal_run_id=f"cancel-transient-{index}",
            )
            StateFactory(
                workflow_run=workflow_run,
                status=source_status,
                timestamp=make_aware(datetime.now() + timedelta(hours=20)),
            )
            workflow_runs.append(workflow_run)

        response = self.client.post(
            self.cancel_endpoint,
            data={
                "workflowrunOrcabusIds": [
                    workflow_run.orcabus_id for workflow_run in workflow_runs
                ],
                "comment": "cancel transient runs",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["createdCount"], len(source_statuses))
        for workflow_run in workflow_runs:
            self.assertTrue(
                State.objects.filter(
                    workflow_run=workflow_run,
                    status="CANCELLED",
                    comment="cancel transient runs",
                ).exists()
            )
        self.assertEqual(mock_emit_wrsc.call_count, len(source_statuses))
        self.assertTrue(
            all(
                call.args[0]["status"] == "CANCELLED"
                for call in mock_emit_wrsc.call_args_list
            )
        )

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_cancel_rejects_existing_excluded_states(self, mock_emit_wrsc):
        source_statuses = [
            "SUCCEEDED",
            "FAILED",
            "ABORTED",
            "RESOLVED",
            "DEPRECATED",
            "CANCELLED",
        ]
        workflow_runs = []
        for index, source_status in enumerate(source_statuses):
            workflow_run = WorkflowRunFactory(
                workflow=self.wf,
                portal_run_id=f"cancel-terminal-{index}",
            )
            StateFactory(
                workflow_run=workflow_run,
                status=source_status,
                timestamp=make_aware(datetime.now() + timedelta(hours=20)),
            )
            workflow_runs.append(workflow_run)

        response = self.client.post(
            self.cancel_endpoint,
            data={
                "workflowrunOrcabusIds": [
                    workflow_run.orcabus_id for workflow_run in workflow_runs
                ],
                "comment": "should fail",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["createdCount"], 0)
        self.assertEqual(data["failedCount"], len(source_statuses))
        self.assertTrue(
            all(
                failure["reason"] == "INVALID_TRANSITION"
                for failure in data["failures"]
            )
        )
        already_cancelled_workflow_run = workflow_runs[
            source_statuses.index("CANCELLED")
        ]
        self.assertEqual(
            State.objects.filter(
                workflow_run=already_cancelled_workflow_run,
                status="CANCELLED",
            ).count(),
            1,
        )
        mock_emit_wrsc.assert_not_called()

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_state_transition_wrsc_failure_rolls_back_state(self, mock_emit_wrsc):
        mock_emit_wrsc.side_effect = RuntimeError("event bus unavailable")

        response = self.client.post(
            self.resolve_endpoint,
            data={
                "workflowrunOrcabusIds": [self.wfr_failed.orcabus_id],
                "comment": "resolved ok",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 502)
        data = response.json()
        self.assertEqual(data["createdCount"], 0)
        self.assertEqual(data["failedCount"], 1)
        self.assertEqual(data["failures"][0]["reason"], "WRSC_EMIT_FAILED")
        self.assertFalse(
            State.objects.filter(
                workflow_run=self.wfr_failed,
                status="RESOLVED",
            ).exists()
        )
        mock_emit_wrsc.assert_called_once()

    @patch(
        "workflow_manager.viewsets.state.WorkflowRunStateTransitionViewSet.create_state_and_emit_wrsc",
        side_effect=DatabaseError("database unavailable"),
    )
    def test_state_transition_database_failure_rolls_back_state(
        self, mock_create_state_and_emit_wrsc
    ):
        response = self.client.post(
            self.resolve_endpoint,
            data={
                "workflowrunOrcabusIds": [self.wfr_failed.orcabus_id],
                "comment": "resolved ok",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data["createdCount"], 0)
        self.assertEqual(data["failedCount"], 1)
        self.assertEqual(data["failures"][0]["reason"], "STATE_CREATION_FAILED")
        self.assertFalse(
            State.objects.filter(
                workflow_run=self.wfr_failed,
                status="RESOLVED",
            ).exists()
        )
        mock_create_state_and_emit_wrsc.assert_called_once()

    def test_superseded_state_transition_routes_are_not_available(self):
        detail_urls = [
            f"{self.endpoint}/{self.wfr_failed.orcabus_id}/deprecate/",
            f"{self.endpoint}/{self.wfr_failed.orcabus_id}/resolve/",
            f"{self.endpoint}/{self.wfr_failed.orcabus_id}/cancel/",
        ]
        for url in detail_urls:
            with self.subTest(url=url):
                response = self.client.post(
                    url,
                    data={"comment": "old route"},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 404)

        response = self.client.post(
            f"/{api_base}workflowrun/state/batch-state-transition/",
            data={
                "workflowrunOrcabusIds": [self.wfr_failed.orcabus_id],
                "status": "RESOLVED",
                "comment": "old route",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

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
        self.assertIn(
            "Invalid state status to update comment.", response.json()["detail"]
        )

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_update_state_comment_success(self, mock_emit_wrsc):
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
        mock_emit_wrsc.assert_not_called()

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

    def test_update_prefetched_objects_cache_invalidation_runs_with_patched_get_object(
        self,
    ):
        """
        Keep direct coverage on the cache invalidation assignment itself.
        This branch only runs when get_object() returns an instance that was
        previously fetched with prefetch_related().
        """
        from workflow_manager.viewsets.state import StateViewSet

        viewset = StateViewSet()
        request = MagicMock()
        request.data = {"comment": "new patched"}
        viewset.get_success_headers = MagicMock(return_value={})

        state_deprecated = StateFactory(
            workflow_run=self.wfr_failed,
            status="DEPRECATED",
            timestamp=make_aware(datetime.now() + timedelta(hours=21)),
            comment="old",
        )
        state_deprecated._prefetched_objects_cache = {"states": [self.state_ready]}
        state_deprecated.save = MagicMock()

        with patch.object(viewset, "get_object", return_value=state_deprecated):
            response = viewset.update(request, partial=True)

        self.assertEqual(response.status_code, 200)
        state_deprecated.save.assert_called_once_with(update_fields=["comment"])
        self.assertEqual(state_deprecated._prefetched_objects_cache, {})
        self.assertEqual(state_deprecated.comment, "new patched")

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_state_transition_success_returns_summary(self, mock_emit_wrsc):
        response = self.client.post(
            self.deprecate_endpoint,
            data={
                "workflowrunOrcabusIds": [
                    self.wfr_succeeded.orcabus_id,
                    self.wfr_empty.orcabus_id,
                ],
                "comment": "bulk deprecated",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["createdCount"], 2)
        self.assertEqual(data["failedCount"], 0)
        self.assertCountEqual(
            data["workflowrunOrcabusIds"],
            [self.wfr_succeeded.orcabus_id, self.wfr_empty.orcabus_id],
        )
        self.assertTrue(
            State.objects.filter(
                workflow_run=self.wfr_succeeded,
                status="DEPRECATED",
                comment="bulk deprecated",
            ).exists()
        )
        self.assertEqual(mock_emit_wrsc.call_count, 2)
        wrsc_events = [call.args[0] for call in mock_emit_wrsc.call_args_list]
        self.assertTrue(all("payload" not in event for event in wrsc_events))
        self.assertCountEqual(
            [event["orcabusId"] for event in wrsc_events],
            [self.wfr_succeeded.orcabus_id, self.wfr_empty.orcabus_id],
        )
        self.assertTrue(
            State.objects.filter(
                workflow_run=self.wfr_empty,
                status="DEPRECATED",
                comment="bulk deprecated",
            ).exists()
        )

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_state_transition_rolls_back_only_failed_emit_item(self, mock_emit_wrsc):
        mock_emit_wrsc.side_effect = [
            {"FailedEntryCount": 0, "Entries": [{}]},
            RuntimeError("event bus unavailable"),
        ]
        response = self.client.post(
            self.deprecate_endpoint,
            data={
                "workflowrunOrcabusIds": [
                    self.wfr_succeeded.orcabus_id,
                    self.wfr_empty.orcabus_id,
                ],
                "comment": "bulk deprecated",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 207)
        data = response.json()
        self.assertEqual(data["createdCount"], 1)
        self.assertEqual(data["failedCount"], 1)
        self.assertEqual(data["workflowrunOrcabusIds"], [self.wfr_succeeded.orcabus_id])
        self.assertEqual(
            data["failures"][0]["workflowrunOrcabusId"],
            self.wfr_empty.orcabus_id,
        )
        self.assertEqual(data["failures"][0]["reason"], "WRSC_EMIT_FAILED")
        self.assertTrue(
            State.objects.filter(
                workflow_run=self.wfr_succeeded,
                status="DEPRECATED",
                comment="bulk deprecated",
            ).exists()
        )
        self.assertFalse(
            State.objects.filter(
                workflow_run=self.wfr_empty,
                status="DEPRECATED",
                comment="bulk deprecated",
            ).exists()
        )
        self.assertEqual(mock_emit_wrsc.call_count, 2)

    @patch(
        "workflow_manager.viewsets.state.WorkflowRunStateTransitionViewSet.create_state_and_emit_wrsc",
        side_effect=DatabaseError("database unavailable"),
    )
    def test_state_transition_database_failure_returns_failure_response(
        self, mock_create_state_and_emit_wrsc
    ):
        response = self.client.post(
            self.deprecate_endpoint,
            data={
                "workflowrunOrcabusIds": [self.wfr_succeeded.orcabus_id],
                "comment": "bulk deprecated",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data["createdCount"], 0)
        self.assertEqual(data["failedCount"], 1)
        self.assertEqual(
            data["failures"][0]["workflowrunOrcabusId"],
            self.wfr_succeeded.orcabus_id,
        )
        self.assertEqual(data["failures"][0]["reason"], "STATE_CREATION_FAILED")
        self.assertNotIn("error", data["failures"][0])
        self.assertFalse(
            State.objects.filter(
                workflow_run=self.wfr_succeeded,
                status="DEPRECATED",
                comment="bulk deprecated",
            ).exists()
        )
        mock_create_state_and_emit_wrsc.assert_called_once()

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_state_transition_returns_partial_success_for_invalid_item(
        self, mock_emit_wrsc
    ):
        response = self.client.post(
            self.resolve_endpoint,
            data={
                "workflowrunOrcabusIds": [
                    self.wfr_failed.orcabus_id,
                    self.wfr_succeeded.orcabus_id,
                ],
                "comment": "bulk resolve",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 207)
        data = response.json()
        self.assertEqual(data["createdCount"], 1)
        self.assertEqual(data["failedCount"], 1)
        self.assertEqual(data["workflowrunOrcabusIds"], [self.wfr_failed.orcabus_id])
        self.assertEqual(
            data["failures"][0]["workflowrunOrcabusId"],
            self.wfr_succeeded.orcabus_id,
        )
        self.assertEqual(data["failures"][0]["reason"], "INVALID_TRANSITION")
        self.assertTrue(
            State.objects.filter(
                workflow_run=self.wfr_failed,
                status="RESOLVED",
                comment="bulk resolve",
            ).exists()
        )
        self.assertFalse(
            State.objects.filter(
                workflow_run=self.wfr_succeeded,
                status="RESOLVED",
                comment="bulk resolve",
            ).exists()
        )
        mock_emit_wrsc.assert_called_once()

    def test_state_transition_requires_fields(self):
        response = self.client.post(
            self.deprecate_endpoint, data={}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_state_transition_rejects_unknown_workflowrun(self):
        response = self.client.post(
            self.deprecate_endpoint,
            data={
                "workflowrunOrcabusIds": ["wfr.non-existing-id"],
                "comment": "bulk deprecated",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["createdCount"], 0)
        self.assertEqual(data["failedCount"], 1)
        self.assertEqual(
            data["failures"][0]["workflowrunOrcabusId"], "wfr.non-existing-id"
        )
        self.assertEqual(data["failures"][0]["reason"], "NOT_FOUND")

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_state_transition_accepts_ids_without_prefix_and_returns_prefixed_ids(
        self, mock_emit_wrsc
    ):
        response = self.client.post(
            self.deprecate_endpoint,
            data={
                "workflowrunOrcabusIds": [
                    self.wfr_succeeded.orcabus_id.replace("wfr.", "", 1),
                    self.wfr_empty.orcabus_id.replace("wfr.", "", 1),
                ],
                "comment": "bulk deprecated no prefix",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertCountEqual(
            data["workflowrunOrcabusIds"],
            [self.wfr_succeeded.orcabus_id, self.wfr_empty.orcabus_id],
        )
        self.assertEqual(mock_emit_wrsc.call_count, 2)

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_state_transition_accepts_csv_orcabus_ids(self, mock_emit_wrsc):
        response = self.client.post(
            self.deprecate_endpoint,
            data={
                "workflowrunOrcabusIds": "{},{}".format(
                    self.wfr_succeeded.orcabus_id.replace("wfr.", "", 1),
                    self.wfr_empty.orcabus_id.replace("wfr.", "", 1),
                ),
                "comment": "bulk deprecated csv ids",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["createdCount"], 2)
        self.assertCountEqual(
            data["workflowrunOrcabusIds"],
            [self.wfr_succeeded.orcabus_id, self.wfr_empty.orcabus_id],
        )
        self.assertEqual(mock_emit_wrsc.call_count, 2)

    @patch("workflow_manager.viewsets.state.emit_wrsc_api_event")
    def test_state_transition_accepts_form_urlencoded_camelcase_csv_orcabus_ids(
        self, mock_emit_wrsc
    ):
        response = self.client.post(
            self.deprecate_endpoint,
            data="workflowrunOrcabusIds={}&comment=Second%20state%20transition.".format(
                "{},{}".format(
                    self.wfr_succeeded.orcabus_id.replace("wfr.", "", 1),
                    self.wfr_empty.orcabus_id.replace("wfr.", "", 1),
                )
            ),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 201, response.content.decode())
        data = response.json()
        self.assertEqual(data["createdCount"], 2)
        self.assertCountEqual(
            data["workflowrunOrcabusIds"],
            [self.wfr_succeeded.orcabus_id, self.wfr_empty.orcabus_id],
        )
        self.assertEqual(mock_emit_wrsc.call_count, 2)
