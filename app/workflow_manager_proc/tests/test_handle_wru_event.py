import os
from unittest import mock

from pydantic import ValidationError

from workflow_manager.models import WorkflowRun, Workflow, Library, LibraryAssociation, State, Payload
from workflow_manager.tests.factories import WorkflowFactory
from workflow_manager_proc.lambdas import handle_wru_event
from workflow_manager_proc.tests.case import WorkflowManagerProcUnitTestCase, logger


class WruEventHandlerUnitTests(WorkflowManagerProcUnitTestCase):

    def setUp(self) -> None:
        self.env_mock = mock.patch.dict(os.environ, {"EVENT_BUS_NAME": "FooBus"})
        self.env_mock.start()
        super().setUp()

    def tearDown(self) -> None:
        self.env_mock.stop()
        super().tearDown()

    def test_handle_wru_event_with_legacy_schema(self):
        """
        python manage.py test workflow_manager_proc.tests.test_handle_wru_event.WruEventHandlerUnitTests.test_handle_wru_event_with_legacy_schema
        """
        self.load_mock_wrsc_legacy()

        try:

            handle_wru_event.handler(self.mock_wrsc_legacy, None)

        except ValidationError as e:
            logger.exception(f"THIS ERROR EXCEPTION IS INTENTIONAL FOR TEST. NOT ACTUAL ERROR. \n{e}")

        self.assertRaises(ValidationError)
        self.assertEqual(Workflow.objects.count(), 0)
        self.assertEqual(WorkflowRun.objects.count(), 0)
        self.assertEqual(Library.objects.count(), 0)

    def test_handle_wru_event(self):
        """
        python manage.py test workflow_manager_proc.tests.test_handle_wru_event.WruEventHandlerUnitTests.test_handle_wru_event
        """
        _ = WorkflowFactory()
        self.load_mock_wru_max()

        handle_wru_event.handler(self.event, None)

        self.assertEqual(Workflow.objects.count(), 1)
        self.assertEqual(WorkflowRun.objects.count(), 1)
        self.assertEqual(State.objects.count(), 1)
        self.assertEqual(Payload.objects.count(), 1)
        self.assertEqual(Library.objects.count(), 2)
        self.assertEqual(LibraryAssociation.objects.count(), 2)

    def test_handle_wru_event_min(self):
        """
        python manage.py test workflow_manager_proc.tests.test_handle_wru_event.WruEventHandlerUnitTests.test_handle_wru_event_min
        """
        _ = WorkflowFactory()
        self.load_mock_wru_min()

        handle_wru_event.handler(self.event, None)

        self.assertEqual(Workflow.objects.count(), 1)
        self.assertEqual(WorkflowRun.objects.count(), 1)
        self.assertEqual(State.objects.count(), 1)
        self.assertEqual(Payload.objects.count(), 0)
        self.assertEqual(Library.objects.count(), 2)
        self.assertEqual(LibraryAssociation.objects.count(), 2)
