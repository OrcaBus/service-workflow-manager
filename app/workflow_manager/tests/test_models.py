import logging
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.test import TestCase
from django.utils import timezone

from workflow_manager.models import (
    Analysis,
    AnalysisContext,
    AnalysisRun,
    Comment,
    Library,
    LibraryAssociation,
    Readset,
    RunContext,
    Workflow,
    WorkflowRun,
)
from workflow_manager.models.analysis_context import AnalysisContextUseCase
from workflow_manager.models.run_context import RunContextPlatform, RunContextUseCase

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class WorkflowModelTests(TestCase):

    def test_save_workflow(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_save_workflow
        """
        mock_wfl = Workflow(
            name="test_workflow",
            version="0.0.1",
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
                name="test_workflow",
                version="0.0.1",
                execution_engine="CIA",
                execution_engine_pipeline_id=str(uuid.uuid4()),
            )
            mock_wfl.save()

            mock_wfl2 = Workflow(
                name="test_workflow",
                version="0.0.1",
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
            usecase=AnalysisContextUseCase.COMPUTE.value,
        )
        logger.info(ctx1)
        self.assertEqual(1, AnalysisContext.objects.count())
        self.assertTrue(ctx1.orcabus_id.startswith("anx."))
        self.assertIsNone(ctx1.description)
        self.assertEqual(ctx1.status, "ACTIVE")
        self.assertEqual(ctx1.usecase, "COMPUTE")

    def test_analysis_run_context_model(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_analysis_run_context_model
        """

        ctx1 = RunContext.objects.create(
            name="test_analysis_context_name",
            usecase=RunContextUseCase.COMPUTE.value,
        )
        logger.info(ctx1)
        self.assertEqual(1, RunContext.objects.count())
        self.assertTrue(ctx1.orcabus_id.startswith("rnx."))
        self.assertIsNone(ctx1.description)
        self.assertEqual(ctx1.status, "ACTIVE")
        self.assertEqual(ctx1.usecase, "COMPUTE")

    def test_workflow_run_context_model(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_workflow_run_context_model
        """

        ctx1 = RunContext.objects.create(
            name="test_wfr_context_name",
            usecase=RunContextUseCase.STORAGE.value,
        )
        logger.info(ctx1)
        self.assertEqual(1, RunContext.objects.count())
        self.assertTrue(ctx1.orcabus_id.startswith("rnx."))
        self.assertIsNone(ctx1.description)
        self.assertEqual(ctx1.status, "ACTIVE")
        self.assertEqual(ctx1.usecase, "STORAGE")

    def test_readset_model(self):
        """
        python manage.py test workflow_manager.tests.test_models.WorkflowModelTests.test_readset_model
        """

        rs = Readset.objects.create(
            rgid="CAGCAGTC+ACGCCAAC.4.999999_A00130_0999_BH7TVMDSX7",
            library_id="L2400001",
            library_orcabus_id="lib.01J8ES4ZDRQAP2BN3SDYYV5PKW"
        )
        self.assertEqual(1, Readset.objects.count())
        self.assertTrue(rs.orcabus_id.startswith("fqr."))
        self.assertEqual(rs.rgid, "CAGCAGTC+ACGCCAAC.4.999999_A00130_0999_BH7TVMDSX7")
        self.assertEqual(rs.library_id, "L2400001")
        self.assertEqual(rs.library_orcabus_id, "lib.01J8ES4ZDRQAP2BN3SDYYV5PKW")


class CommentModelTests(TestCase):
    def setUp(self):
        from workflow_manager.tests.factories import WorkflowRunFactory

        self.wfr = WorkflowRunFactory()
        self.analysis_run = AnalysisRun.objects.create(analysis_run_name="TestRun")

    def test_comment_requires_exactly_one_parent(self):
        """Comment must be linked to exactly one of workflow_run or analysis_run."""
        with self.assertRaises(ValidationError):
            Comment(workflow_run=None, analysis_run=None, text="x", created_by="u").save()

        with self.assertRaises(ValidationError):
            Comment(
                workflow_run=self.wfr,
                analysis_run=self.analysis_run,
                text="x",
                created_by="u",
            ).save()

    def test_comment_workflow_run_valid(self):
        c = Comment.objects.create(
            workflow_run=self.wfr, text="test", created_by="user1"
        )
        self.assertEqual(c.workflow_run, self.wfr)
        self.assertIsNone(c.analysis_run)
        self.assertIn("cmt", str(c.orcabus_id))

    def test_comment_analysis_run_valid(self):
        c = Comment.objects.create(
            analysis_run=self.analysis_run, text="test", created_by="user1"
        )
        self.assertEqual(c.analysis_run, self.analysis_run)
        self.assertIsNone(c.workflow_run)

    def test_comment_str(self):
        c = Comment.objects.create(
            workflow_run=self.wfr, text="hello", created_by="u"
        )
        self.assertIn("ID:", str(c))
        self.assertIn("hello", str(c))


class RunContextEnrichmentTests(TestCase):
    """Tests for Phase 1 RunContext model enrichment (RCM-01 through RCM-05)."""

    def test_platform_field_stored_and_returned(self):
        """RCM-01: platform field persists across DB round-trip."""
        ctx = RunContext.objects.create(
            name="icav2-prod", usecase=RunContextUseCase.COMPUTE, platform=RunContextPlatform.ICAV2
        )
        ctx.refresh_from_db()
        self.assertEqual(ctx.platform, "ICAV2")

    def test_all_platform_choices_valid(self):
        """RCM-01: all RunContextPlatform enum values are accepted."""
        for i, platform in enumerate(RunContextPlatform):
            ctx = RunContext.objects.create(
                name=f"ctx-{platform.value}", usecase=RunContextUseCase.COMPUTE, platform=platform
            )
            self.assertEqual(ctx.platform, platform.value)

    def test_data_field_roundtrips(self):
        """RCM-02: data JSONField preserves arbitrary keys across DB round-trip."""
        payload = {"projectId": "proj-abc123", "workspaceId": "ws-xyz"}
        ctx = RunContext.objects.create(
            name="icav2-prod", usecase=RunContextUseCase.COMPUTE,
            platform=RunContextPlatform.ICAV2, data=payload
        )
        ctx.refresh_from_db()
        self.assertEqual(ctx.data, payload)

    def test_data_empty_dict_normalised_to_none(self):
        """RCM-02: empty dict {} is normalised to None by clean()."""
        ctx = RunContext.objects.create(
            name="empty-data", usecase=RunContextUseCase.COMPUTE,
            platform=RunContextPlatform.ICAV2, data={}
        )
        ctx.refresh_from_db()
        self.assertIsNone(ctx.data)

    def test_data_null_by_default(self):
        """RCM-02: data defaults to None when not provided."""
        ctx = RunContext.objects.create(
            name="no-data", usecase=RunContextUseCase.COMPUTE,
            platform=RunContextPlatform.ICAV2
        )
        self.assertIsNone(ctx.data)

    def test_execution_mode_usecase_created(self):
        """RCM-03: EXECUTION_MODE is a valid usecase value."""
        ctx = RunContext.objects.create(
            name="manual", usecase=RunContextUseCase.EXECUTION_MODE
        )
        self.assertEqual(ctx.usecase, "EXECUTION_MODE")
        self.assertIsNone(ctx.platform)

    def test_execution_mode_platform_raises_validation_error(self):
        """D-04: EXECUTION_MODE contexts must have platform=NULL."""
        with self.assertRaises(ValidationError) as cm:
            RunContext.objects.create(
                name="manual", usecase=RunContextUseCase.EXECUTION_MODE,
                platform=RunContextPlatform.ICAV2
            )
        self.assertIn("platform", cm.exception.message_dict)

    def test_unique_constraint_allows_same_name_usecase_different_platform(self):
        """RCM-04: same name+usecase with different platform values coexist."""
        RunContext.objects.create(
            name="prod", usecase=RunContextUseCase.COMPUTE, platform=RunContextPlatform.ICAV2
        )
        RunContext.objects.create(
            name="prod", usecase=RunContextUseCase.COMPUTE, platform=RunContextPlatform.SEQERA
        )
        self.assertEqual(RunContext.objects.filter(name="prod").count(), 2)

    def test_unique_constraint_nulls_not_distinct(self):
        """RCM-04: two rows with same name+usecase+NULL platform violate constraint.

        Django 5.2 enforce UniqueConstraint(nulls_distinct=False) at the full_clean()
        layer (raising ValidationError) before the DB-level IntegrityError fires.
        """
        RunContext.objects.create(
            name="legacy", usecase=RunContextUseCase.COMPUTE, platform=None
        )
        with self.assertRaises((IntegrityError, ValidationError)):
            RunContext.objects.create(
                name="legacy", usecase=RunContextUseCase.COMPUTE, platform=None
            )

    def test_platform_nullable(self):
        """RCM-05: platform can be omitted (defaults to None)."""
        ctx = RunContext.objects.create(
            name="no-platform", usecase=RunContextUseCase.STORAGE
        )
        self.assertIsNone(ctx.platform)

    def test_legacy_row_unaffected(self):
        """RCM-05: old-style RunContext (no platform, no data) still works."""
        ctx = RunContext.objects.create(
            name="old-context", usecase=RunContextUseCase.STORAGE
        )
        self.assertIsNone(ctx.platform)
        self.assertIsNone(ctx.data)
        self.assertEqual(ctx.status, "ACTIVE")
        self.assertTrue(ctx.orcabus_id.startswith("rnx."))
