import logging
import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from workflow_manager.models import Library, WorkflowRun, LibraryAssociation
from workflow_manager.models.workflow import Workflow

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class WorkflowModelTests(TestCase):

    def test_save_workflow(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_save_workflow
        """
        mock_wfl = Workflow(
            workflow_name="test_workflow",
            workflow_version="0.0.1",
            execution_engine="CIA",
            execution_engine_pipeline_id=str(uuid.uuid4()),
        )
        mock_wfl.save()

        logger.info(mock_wfl)
        logger.info(mock_wfl.execution_engine_pipeline_id)

        self.assertEqual(1, Workflow.objects.count())
        self.assertTrue(mock_wfl.orcabus_id.startswith("wfl."))

    def test_save_workflow_fail(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_save_workflow_fail
        """

        try:
            mock_wfl = Workflow(
                workflow_name="test_workflow",
                workflow_version="0.0.1",
                execution_engine="CIA",
                execution_engine_pipeline_id=str(uuid.uuid4()),
            )
            mock_wfl.save()

            mock_wfl2 = Workflow(
                workflow_name="test_workflow",
                workflow_version="0.0.1",
                execution_engine="CIA",
                execution_engine_pipeline_id=str(uuid.uuid4()),
            )
            mock_wfl2.save()

        except ValidationError as e:
            logger.exception(f"THIS ERROR EXCEPTION IS INTENTIONAL FOR TEST. NOT ACTUAL ERROR. \n{e}")

        self.assertRaises(ValidationError)

    def test_save_library(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_save_library
        """

        lib = Library(
            library_id="L2400001"
        )
        lib.save()
        logger.info(lib)
        self.assertEqual(1, Library.objects.count())
        self.assertTrue(lib.orcabus_id.startswith("lib."))

    def test_save_library_with_orcabus_id(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_save_library_with_orcabus_id
        """

        lib = Library(
            library_id="L2400001",
            orcabus_id="lib.01J8ES4ZDRQAP2BN3SDYYV5PKW"
        )
        lib.save()
        logger.info(lib)
        self.assertEqual(1, Library.objects.count())
        self.assertTrue(lib.orcabus_id.startswith("lib."))

    def test_workflow_run_libraries(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_workflow_run_libraries
        """

        lib1 = Library.objects.create(library_id="L2400001")
        lib2 = Library.objects.create(library_id="L2400002")
        wfr = WorkflowRun.objects.create(
            portal_run_id="99990101abcdefgh"
        )
        LibraryAssociation.objects.create(
            library=lib1,
            workflow_run=wfr,
            association_date=timezone.now(),
            status="ACTIVE",
        )
        LibraryAssociation.objects.create(
            library=lib2,
            workflow_run=wfr,
            association_date=timezone.now(),
            status="ACTIVE",
        )

        for lib in wfr.libraries.all():
            logger.info(lib)

        self.assertEqual(2, len(Library.objects.all()))
