import logging
from unittest.mock import patch
from django.test import TestCase
import botocore.session
from botocore.stub import Stubber
from unittest.mock import patch

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class WorkflowManagerProcUnitTestCase(TestCase):

    def setUp(self) -> None:
        # Mock boto3 client
        self.events_client = botocore.session.get_session().create_client('events', region_name='ap-southeast-2')
        self.boto3_patcher = patch('workflow_manager_proc.services.emit_workflow_run_state_change.client', return_value=self.events_client)
        self.mock_boto3 = self.boto3_patcher.start()
        self.mock_events = self.mock_boto3.return_value
        self.events_client_stubber = Stubber(self.events_client)
        self.events_client_stubber.activate()
        super().setUp()

    def tearDown(self) -> None:
        self.events_client_stubber.deactivate()
        self.boto3_patcher.stop()
        super().tearDown()


class WorkflowManagerProcIntegrationTestCase(TestCase):
    pass
