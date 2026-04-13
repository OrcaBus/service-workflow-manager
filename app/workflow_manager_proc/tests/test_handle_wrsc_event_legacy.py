import os
from unittest import mock

from workflow_manager.models import WorkflowRun, Workflow, Library
from workflow_manager_proc.lambdas import handle_wrsc_event_legacy
from workflow_manager_proc.tests.case import WorkflowManagerProcUnitTestCase, logger


class LegacyWrscEventHandlerUnitTests(WorkflowManagerProcUnitTestCase):

    def setUp(self) -> None:
        self.env_mock = mock.patch.dict(os.environ, {"EVENT_BUS_NAME": "FooBus"})
        self.env_mock.start()
        super().setUp()

    def tearDown(self) -> None:
        self.env_mock.stop()
        super().tearDown()

    def test_handle_wrsc_event_legacy(self):
        """
        python manage.py test workflow_manager_proc.tests.test_handle_wrsc_event_legacy.LegacyWrscEventHandlerUnitTests.test_handle_wrsc_event_legacy
        """
        self.load_mock_wrsc_legacy()

        event_dict = self.event

        handle_wrsc_event_legacy.handler(event_dict, None)

        self.assertIsNotNone(event_dict["detail"]["workflowName"])
        self.assertIsNotNone(event_dict["detail"]["workflowVersion"])
        self.assertEqual(Workflow.objects.count(), 1)
        self.assertEqual(WorkflowRun.objects.count(), 1)
        self.assertEqual(Library.objects.count(), 2)

    def test_handle_wrsc_event_legacy_with_new_schema(self):
        """
        python manage.py test workflow_manager_proc.tests.test_handle_wrsc_event_legacy.LegacyWrscEventHandlerUnitTests.test_handle_wrsc_event_legacy_with_new_schema
        """
        self.load_mock_wru_max()

        event_dict = self.event

        try:

            handle_wrsc_event_legacy.handler(event_dict, None)

        except ValueError as e:
            logger.exception(f"THIS ERROR EXCEPTION IS INTENTIONAL FOR TEST. NOT ACTUAL ERROR. \n{e}")

        self.assertRaises(ValueError)
        self.assertEqual(Workflow.objects.count(), 0)
        self.assertEqual(WorkflowRun.objects.count(), 0)
        self.assertEqual(Library.objects.count(), 0)
