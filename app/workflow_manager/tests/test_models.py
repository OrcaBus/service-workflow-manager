import logging
import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from workflow_manager.models import Library, WorkflowRun, LibraryAssociation, Analysis, AnalysisContext
from workflow_manager.models.analysis_run_context import AnalysisRunContext
from workflow_manager.models.workflow import Workflow
from workflow_manager.models.workflow_run_context import WorkflowRunContext

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
            execution_engine="ICA",
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

    def test_analysis_model(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_analysis_model
        """

        ana1 = Analysis.objects.create(
            analysis_name="test_analysis_name",
            analysis_version="0.0.1",
        )
        self.assertEqual(1, Analysis.objects.count())
        self.assertTrue(ana1.orcabus_id.startswith("ana."))
        self.assertIsNone(ana1.description)
        self.assertEqual(ana1.status, "ACTIVE")

    def test_analysis_context_model(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_analysis_context_model
        """

        ctx1 = AnalysisContext.objects.create(
            name="test_analysis_context_name",
            usecase="test_analysis_context_usecase",
        )
        self.assertEqual(1, AnalysisContext.objects.count())
        self.assertTrue(ctx1.orcabus_id.startswith("anx."))
        self.assertIsNone(ctx1.description)
        self.assertEqual(ctx1.status, "ACTIVE")

    def test_analysis_run_context_model(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_analysis_run_context_model
        """

        ctx1 = AnalysisRunContext.objects.create(
            name="test_analysis_context_name",
            usecase="test_analysis_context_usecase",
        )
        self.assertEqual(1, AnalysisRunContext.objects.count())
        self.assertTrue(ctx1.orcabus_id.startswith("arx."))
        self.assertIsNone(ctx1.description)
        self.assertEqual(ctx1.status, "ACTIVE")

    def test_workflow_run_context_model(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_workflow_run_context_model
        """

        ctx1 = WorkflowRunContext.objects.create(
            name="test_wfr_context_name",
            usecase="test_wfr_context_usecase",
        )
        self.assertEqual(1, WorkflowRunContext.objects.count())
        self.assertTrue(ctx1.orcabus_id.startswith("wrx."))
        self.assertIsNone(ctx1.description)
        self.assertEqual(ctx1.status, "ACTIVE")
