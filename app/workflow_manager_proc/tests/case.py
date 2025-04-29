import logging
from unittest.mock import patch
from django.test import TestCase

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class WorkflowManagerProcUnitTestCase(TestCase):

    def setUp(self) -> None:
        # Mock boto3 client
        self.boto3_patcher = patch('boto3.client')
        self.mock_boto3 = self.boto3_patcher.start()
        self.mock_events = self.mock_boto3.return_value
        super().setUp()

    def tearDown(self) -> None:
        self.boto3_patcher.stop()
        super().tearDown()


class WorkflowManagerProcIntegrationTestCase(TestCase):
    pass
