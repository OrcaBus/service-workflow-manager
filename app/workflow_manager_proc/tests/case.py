import json
import logging
import os
from unittest.mock import patch

import botocore.session
from botocore.stub import Stubber
from django.test import TestCase

from workflow_manager_proc.domain.event.wrsc import AWSEvent, WorkflowRunStateChange

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class WorkflowManagerProcUnitTestCase(TestCase):

    def setUp(self) -> None:
        # Mock boto3 client
        self.events_client = botocore.session.get_session().create_client('events', region_name='ap-southeast-2')
        self.boto3_patcher = patch('workflow_manager_proc.services.event_utils.client', return_value=self.events_client)
        self.mock_boto3 = self.boto3_patcher.start()
        self.mock_events = self.mock_boto3.return_value
        self.events_client_stubber = Stubber(self.events_client)
        self.events_client_stubber.activate()
        super().setUp()

    def tearDown(self) -> None:
        self.events_client_stubber.deactivate()
        self.boto3_patcher.stop()
        super().tearDown()

    def load_mock_file(self, rel_path):
        script_dir = os.path.dirname(__file__)
        logger.info(f"Loading test event data from {rel_path}")
        abs_file_path = os.path.join(script_dir, rel_path)
        with open(abs_file_path) as f:
            file_content = f.read()
            self.event: dict = json.loads(file_content)

    def load_mock_wrsc_max(self):
        self.load_mock_file(rel_path="fixtures/WRSC_max.json")
        mock_obj_with_envelope: AWSEvent = AWSEvent.model_validate(self.event)
        self.mock_wrsc_max: WorkflowRunStateChange = mock_obj_with_envelope.detail

    def load_mock_wrsc_min(self):
        self.load_mock_file(rel_path="fixtures/WRSC_min.json")
        mock_obj_with_envelope: AWSEvent = AWSEvent.model_validate(self.event)
        self.mock_wrsc_min: WorkflowRunStateChange = mock_obj_with_envelope.detail

    def load_mock_wrsc_legacy(self):
        self.load_mock_file(rel_path="fixtures/WRSC_legacy.json")
        self.mock_wrsc_legacy = self.event


class WorkflowManagerProcIntegrationTestCase(TestCase):
    pass
