import json
import os
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from django.test import TestCase
from django.utils.timezone import make_aware
from libumccr.aws import libeb

from workflow_manager.models import LibraryAssociation, Payload, Workflow, WorkflowRun
from workflow_manager.tests.factories import StateFactory, WorkflowRunFactory, PayloadFactory
from workflow_manager.tests.fixtures.sim_workflow import TestData
from workflow_manager.urls.base import api_base


class WorkflowRunRerunViewSetTestCase(TestCase):
    endpoint = f"/{api_base}workflowrun"

    def setUp(self):
        os.environ["EVENT_BUS_NAME"] = "mock-bus"
        TestData().create_primary()

        self._real_emit_event = libeb.emit_event
        libeb.emit_event = MagicMock()

    def tearDown(self) -> None:
        libeb.emit_event = self._real_emit_event

    def _assert_wru_response_structure(self, response_data: dict, expected_dataset: str):
        """Assert the response conforms to the WorkflowRunUpdate (WRU) schema."""
        self.assertEqual(response_data["status"], "READY")
        self.assertIn("portalRunId", response_data)
        self.assertIn("workflowRunName", response_data)
        self.assertIn("timestamp", response_data)

        # workflow must be a nested object (not flat workflowName/workflowVersion)
        workflow = response_data["workflow"]
        self.assertIsInstance(workflow, dict)
        self.assertIn("orcabusId", workflow)
        self.assertIn("name", workflow)
        self.assertIn("version", workflow)

        # libraries (not linkedLibraries)
        self.assertIn("libraries", response_data)
        self.assertNotIn("linkedLibraries", response_data)
        self.assertIsInstance(response_data["libraries"], list)
        for lib in response_data["libraries"]:
            self.assertIn("libraryId", lib)
            self.assertIn("orcabusId", lib)

        # payload with overridden dataset
        payload = response_data["payload"]
        self.assertIn("version", payload)
        self.assertIn("data", payload)
        self.assertEqual(payload["data"]["inputs"]["dataset"], expected_dataset)

    def test_rerun_api(self):
        wfl_run = WorkflowRun.objects.all().first()
        payload = wfl_run.states.get(status="READY").payload
        payload.data = {
            "inputs": {
                "someUri": "s3://random/prefix/",
                "dataset": "BRCA",
            },
            "engineParameters": {
                "sourceUri": f"s3://bucket/{wfl_run.portal_run_id}/",
            },
        }
        payload.save()

        response = self.client.post(f"{self.endpoint}/{wfl_run.orcabus_id}/rerun")
        self.assertEqual(response.status_code, 400, "Workflow name associated with the workflow run is not allowed")

        wfl = Workflow.objects.all().first()
        wfl.name = "rnasum"
        wfl.save()

        response = self.client.post(
            f"{self.endpoint}/{wfl_run.orcabus_id}/rerun",
            data={"dataset": "INVALID_CHOICE"},
        )
        self.assertEqual(response.status_code, 400, "Invalid payload expected")

        response = self.client.post(f"{self.endpoint}/{wfl_run.orcabus_id}/rerun", data={"dataset": "PANCAN"})
        self.assertEqual(response.status_code, 200, "Expected a successful response")
        response_data = response.json()

        # Verify the response conforms to the WRU schema
        self._assert_wru_response_structure(response_data, expected_dataset="PANCAN")

        # The portalRunId must be a newly generated value, not the original one
        new_portal_run_id = response_data["portalRunId"]
        self.assertNotEqual(new_portal_run_id, wfl_run.portal_run_id)

        # Verify old portal_run_id in payload data is replaced with new one
        source_uri = response_data["payload"]["data"]["engineParameters"]["sourceUri"]
        self.assertNotIn(wfl_run.portal_run_id, source_uri, "Old portal_run_id should be replaced in payload data")
        self.assertIn(new_portal_run_id, source_uri, "New portal_run_id should appear in payload data")

        # Verify libeb.emit_event was called with correct WRU DetailType
        libeb.emit_event.assert_called()
        call_args = libeb.emit_event.call_args[0][0]
        self.assertEqual(call_args["DetailType"], "WorkflowRunUpdate")
        self.assertEqual(call_args["Source"], "orcabus.workflowmanagerapi")

        # EventBridge detail must omit optional fields instead of null (JSON schema: optional string, not nullable)
        detail_obj = json.loads(call_args["Detail"])
        for omitted_top_level in ("id", "version", "orcabusId", "analysisRun", "computeEnv", "storageEnv"):
            self.assertNotIn(
                omitted_top_level,
                detail_obj,
                f"Optional WRU field {omitted_top_level!r} should be omitted, not emitted as null",
            )

        response = self.client.post(f"{self.endpoint}/{wfl_run.orcabus_id}/rerun", data={"dataset": "BRCA"})
        self.assertEqual(response.status_code, 400, "Rerun duplication with same input error expected")

        response = self.client.post(
            f"{self.endpoint}/{wfl_run.orcabus_id}/rerun",
            data={"dataset": "BRCA", "allow_duplication": True},
        )
        self.assertEqual(
            response.status_code,
            200,
            "Rerun with same input allowed when `allow_duplication` is set to True",
        )

        # Unique Library Test - library IDs are treated as a unique set
        wfr_new = WorkflowRunFactory(
            workflow_run_name="AdditionalTestWorkflowRun",
            portal_run_id="9876",
            workflow=wfl,
        )
        new_payload = Payload.objects.create(
            version="1.0.0",
            payload_ref_id="01H6GZ8X4YJ5V9Q2F7A3B6CDE8",
            data={
                "inputs": {
                    "someUri": "s3://random/prefix/",
                    "dataset": "PANCAN",
                },
                "engineParameters": {
                    "sourceUri": f"s3://bucket/{wfr_new.portal_run_id}/",
                },
            },
        )
        for i, state in enumerate(["DRAFT", "READY", "RUNNING", "SUCCEEDED"]):
            StateFactory(
                workflow_run=wfr_new,
                status=state,
                payload=new_payload,
                timestamp=make_aware(datetime.now() + timedelta(hours=i)),
            )
        LibraryAssociation.objects.create(
            workflow_run=wfr_new,
            library=wfl_run.libraries.all().first(),
            association_date=make_aware(datetime.now()),
            status="ACTIVE",
        )

        # This will trigger the rerun with different library set
        response = self.client.post(f"{self.endpoint}/{wfr_new.orcabus_id}/rerun", data={"dataset": "BRCA"})
        self.assertEqual(
            response.status_code,
            200,
            "Rerun with the same input is allowed when using a different library set",
        )

    def test_rerun_comment_append(self):
        """Verify that successive reruns append to the existing comment rather than overwriting."""
        wfl_run = WorkflowRun.objects.all().first()
        payload = wfl_run.states.get(status="READY").payload
        payload.data = {
            "inputs": {"someUri": "s3://random/prefix/", "dataset": "BRCA"},
            "engineParameters": {"sourceUri": "s3://bucket/test/"},
        }
        payload.save()

        wfl = Workflow.objects.all().first()
        wfl.name = "rnasum"
        wfl.save()

        original_comment = wfl_run.comment

        # First rerun
        response = self.client.post(f"{self.endpoint}/{wfl_run.orcabus_id}/rerun", data={"dataset": "PANCAN"})
        self.assertEqual(response.status_code, 200)
        first_portal_run_id = response.json()["portalRunId"]

        wfl_run.refresh_from_db()
        if original_comment:
            self.assertIn(original_comment, wfl_run.comment, "Original comment should be preserved")
        self.assertIn(first_portal_run_id, wfl_run.comment)

        # Second rerun (allow duplication)
        response = self.client.post(
            f"{self.endpoint}/{wfl_run.orcabus_id}/rerun",
            data={"dataset": "PANCAN", "allow_duplication": True},
        )
        self.assertEqual(response.status_code, 200)
        second_portal_run_id = response.json()["portalRunId"]

        wfl_run.refresh_from_db()
        self.assertIn(first_portal_run_id, wfl_run.comment, "First rerun comment should still be present")
        self.assertIn(second_portal_run_id, wfl_run.comment, "Second rerun comment should be appended")

    def test_rerun_duplication_skips_runs_without_ready_state(self):
        """
        Ensure rerun duplication logic skips workflow runs that do not have a READY state (i.e., when the READY state does not exist for a run).
        This test verifies that the rerun process continues correctly and does not fail or duplicate runs when a related WorkflowRun is missing the READY state.
        """
        # Both wfr_run used below use the same workflow, and need to change to rnasum to allow rerun and trigger the
        # duplication logic
        wfl = Workflow.objects.all().first()
        wfl.name = "rnasum"
        wfl.save()

        # The workflowrun that needs to exist as part of rerun
        wfl_run1 = WorkflowRun.objects.get(workflow_run_name="TestWorkflowPrimaryRun1")
        payload = wfl_run1.states.get(status="READY").payload
        payload.data = {
            "inputs": {
                "someUri": "s3://random/prefix/",
                "dataset": "BRCA",
            },
            "engineParameters": {
                "sourceUri": f"s3://bucket/{wfl_run1.portal_run_id}/",
            },
        }
        payload.save()

        # The workflowrun that exists with the same libraries but has the READY state removed
        wfl_run2 = WorkflowRun.objects.get(workflow_run_name="TestWorkflowPrimaryRun2")
        wfl_run2.states.get(status="READY").delete()

        response = self.client.post(f"{self.endpoint}/{wfl_run1.orcabus_id}/rerun", data={"dataset": "PANCAN"})
        self.assertEqual(response.status_code, 200, "Expected a successful response")

    def test_rerun_wfr_same_deprecated_payload(self):
        """The exact same rnasum payload but the old one has deprecated and now expected to rerun the same thing"""

        # Both wfr_run used below use the same workflow, and need to change to rnasum to allow rerun and trigger the
        # duplication logic
        wfl = Workflow.objects.all().first()
        wfl.name = "rnasum"
        wfl.save()

        # The workflowrun that needs to exist as part of rerun
        wfl_run1 = WorkflowRun.objects.get(workflow_run_name="TestWorkflowPrimaryRun1")
        payload = wfl_run1.states.get(status="READY").payload
        payload.data = {
            "inputs": {
                "someUri": "s3://random/prefix/",
                "dataset": "BRCA",
            },
            "engineParameters": {
                "sourceUri": f"s3://bucket/{wfl_run1.portal_run_id}/",
            },
        }
        payload.save()

        wfl_run2 = WorkflowRun.objects.get(workflow_run_name="TestWorkflowPrimaryRun2")

        response = self.client.post(f"{self.endpoint}/{wfl_run1.orcabus_id}/rerun", data={"dataset": "PANCAN"})
        self.assertEqual(response.status_code, 200, "Expected a successful response")

        new_payload2 = Payload.objects.create(
            version="1.0.0",
            payload_ref_id=str(uuid.uuid4()),
            data={
                "inputs": {
                    "someUri": "s3://random/prefix/",
                    "dataset": "PANCAN",
                },
                "engineParameters": {
                    "sourceUri": f"s3://bucket/{wfl_run1.portal_run_id}/",
                },
            },
        )
        ready_state2 = wfl_run2.states.get(status="READY")
        ready_state2.payload = new_payload2
        ready_state2.save()

        StateFactory(
            workflow_run=wfl_run2,
            status="DEPRECATED",
            payload=PayloadFactory(payload_ref_id=str(uuid.uuid4())),
            timestamp=make_aware(datetime.now())
        )
        response = self.client.post(f"{self.endpoint}/{wfl_run1.orcabus_id}/rerun", data={"dataset": "PANCAN"})
        self.assertEqual(response.status_code, 200, "Expected a successful response")

    def test_disable_rerun_deprecated_wfr(self):
        """Test that a workflow run marked as DEPRECATED cannot be rerun."""
        wfl = Workflow.objects.all().first()
        wfl.name = "rnasum"
        wfl.save()

        # The workflowrun that needs to exist as part of rerun
        wfl_run1 = WorkflowRun.objects.get(workflow_run_name="TestWorkflowPrimaryRun1")
        payload = wfl_run1.states.get(status="READY").payload
        payload.data = {
            "inputs": {
                "someUri": "s3://random/prefix/",
                "dataset": "BRCA",
            },
            "engineParameters": {
                "sourceUri": f"s3://bucket/{wfl_run1.portal_run_id}/",
            },
        }
        payload.save()

        # Test if existing wfr is deprecated, it will not allow for rerun
        StateFactory(
            workflow_run=wfl_run1,
            status="DEPRECATED",
            payload=PayloadFactory(payload_ref_id=str(uuid.uuid4())),
            timestamp=make_aware(datetime.now())
        )
        response = self.client.post(f"{self.endpoint}/{wfl_run1.orcabus_id}/rerun", data={"dataset": "BRCA"})
        self.assertEqual(response.status_code, 400, "Expected a fail response")
