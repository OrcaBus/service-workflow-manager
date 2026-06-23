import json
import os
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from workflow_manager.aws_event_bridge.event import (
    EventBridgePublishError,
    emit_wrsc_api_event,
)


class WrscApiEventTestCase(SimpleTestCase):
    def build_event(self):
        return {
            "id": "wrsc-event-id",
            "version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
            "orcabusId": "wfr.01J5M2JFE1JPYV62RYQEG99WR1",
            "portalRunId": "20260623example",
            "executionId": "execution-id",
            "workflowRunName": "example-workflow-run",
            "workflow": {
                "orcabusId": "wfl.01J5M2JFE1JPYV62RYQEG99WFL",
                "name": "example-workflow",
                "version": "1.0.0",
                "codeVersion": "1.0.0",
                "executionEngine": "ICA",
                "executionEnginePipelineId": "pipeline-id",
                "validationState": "VALIDATED",
            },
            "status": "RESOLVED",
        }

    @patch.dict(os.environ, {"EVENT_BUS_NAME": "test-event-bus"})
    @patch("workflow_manager.aws_event_bridge.event.libeb.emit_event")
    def test_emit_wrsc_api_event_omits_payload(self, mock_emit_event):
        mock_emit_event.return_value = {"FailedEntryCount": 0, "Entries": [{}]}

        emit_wrsc_api_event(self.build_event(), attempt_count=2)

        entry = mock_emit_event.call_args.args[0]
        self.assertEqual(entry["Source"], "orcabus.workflowmanager")
        self.assertEqual(entry["DetailType"], "WorkflowRunStateChange")
        self.assertEqual(entry["EventBusName"], "test-event-bus")
        detail = json.loads(entry["Detail"])
        self.assertNotIn("payload", detail)
        self.assertEqual(detail["status"], "RESOLVED")

    @patch.dict(os.environ, {"EVENT_BUS_NAME": "test-event-bus"})
    @patch("workflow_manager.aws_event_bridge.event.libeb.emit_event")
    def test_emit_wrsc_api_event_raises_and_logs_partial_failure(self, mock_emit_event):
        mock_emit_event.return_value = {
            "FailedEntryCount": 1,
            "Entries": [
                {
                    "ErrorCode": "InternalFailure",
                    "ErrorMessage": "EventBridge failed",
                }
            ],
        }

        with self.assertLogs(
            "workflow_manager.aws_event_bridge.event", level="ERROR"
        ) as logs:
            with self.assertRaises(EventBridgePublishError):
                emit_wrsc_api_event(self.build_event())

        self.assertIn("wrsc-event-id", " ".join(logs.output))
        self.assertIn("InternalFailure", " ".join(logs.output))

    @patch.dict(os.environ, {"EVENT_BUS_NAME": "test-event-bus"})
    @patch("workflow_manager.aws_event_bridge.event.libeb.emit_event")
    def test_emit_wrsc_api_event_reraises_sdk_exception(self, mock_emit_event):
        mock_emit_event.side_effect = RuntimeError("network unavailable")

        with self.assertLogs(
            "workflow_manager.aws_event_bridge.event", level="ERROR"
        ) as logs:
            with self.assertRaisesRegex(RuntimeError, "network unavailable"):
                emit_wrsc_api_event(self.build_event(), attempt_count=3)

        logged = " ".join(logs.output)
        self.assertIn("wrsc-event-id", logged)
        self.assertIn("attempt=3", logged)
