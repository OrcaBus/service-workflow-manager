import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from django.test import TestCase
from django.utils.timezone import make_aware
from libumccr.aws import libeb

from workflow_manager.models import LibraryAssociation, Payload, Workflow, WorkflowRun
from workflow_manager.tests.factories import StateFactory, WorkflowRunFactory
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
        self.assertIn(response.status_code, [400], "Workflow name associated with the workflow run is not allowed")

        wfl = Workflow.objects.all().first()
        wfl.name = "rnasum"
        wfl.save()

        response = self.client.post(
            f"{self.endpoint}/{wfl_run.orcabus_id}/rerun",
            data={"dataset": "INVALID_CHOICE"},
        )
        self.assertIn(response.status_code, [400], "Invalid payload expected")

        response = self.client.post(f"{self.endpoint}/{wfl_run.orcabus_id}/rerun", data={"dataset": "PANCAN"})
        self.assertIn(response.status_code, [200], "Expected a successful response")
        self.assertTrue(wfl_run.portal_run_id not in str(response.content), "expect old portal_run_id replaced")

        response = self.client.post(f"{self.endpoint}/{wfl_run.orcabus_id}/rerun", data={"dataset": "BRCA"})
        self.assertIn(response.status_code, [400], "Rerun duplication with same input error expected")

        response = self.client.post(
            f"{self.endpoint}/{wfl_run.orcabus_id}/rerun",
            data={"dataset": "BRCA", "allow_duplication": True},
        )
        self.assertIn(
            response.status_code,
            [200],
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
        self.assertIn(
            response.status_code,
            [200],
            "Rerun with the same input is allowed when using a different library set",
        )
