import os
from unittest import mock

from mockito import when, unstub

from workflow_manager.models import Workflow, WorkflowRun, Library, LibraryAssociation, State, Payload, AnalysisRun
from workflow_manager.tests.factories import WorkflowRunFactory
from workflow_manager_proc.domain.event.wrsc import WorkflowRunStateChange
from workflow_manager_proc.services import workflow_run
from workflow_manager_proc.tests.case import WorkflowManagerProcUnitTestCase, logger


class WorkflowRunSrvUnitTests(WorkflowManagerProcUnitTestCase):

    def setUp(self) -> None:
        self.env_mock = mock.patch.dict(os.environ, {"EVENT_BUS_NAME": "FooBus"})
        self.env_mock.start()
        super().setUp()

    def tearDown(self) -> None:
        self.env_mock.stop()
        unstub()
        super().tearDown()

    def test_create_workflow_run(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_create_workflow_run
        """
        self.load_mock_wrsc_min()
        out_wrsc = workflow_run.create_workflow_run(self.mock_wrsc_min)
        self.assertIsNotNone(out_wrsc)
        self.assertEqual(Workflow.objects.count(), 1)
        self.assertEqual(WorkflowRun.objects.count(), 1)
        self.assertEqual(State.objects.count(), 1)
        self.assertEqual(Payload.objects.count(), 0)

    def test_create_workflow_run_state_has_not_been_updated(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_create_workflow_run_state_has_not_been_updated
        """
        self.load_mock_wrsc_min()
        when(workflow_run).update_workflow_run_to_new_state(...).thenReturn((False, "DOES_NOT_MATTER"))
        out_wrsc = workflow_run.create_workflow_run(self.mock_wrsc_min)
        self.assertIsNone(out_wrsc)
        self.assertEqual(Workflow.objects.count(), 1)
        self.assertEqual(WorkflowRun.objects.count(), 1)
        self.assertEqual(State.objects.count(), 0)
        self.assertEqual(Payload.objects.count(), 0)

    def test_create_or_get_workflow(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_create_or_get_workflow
        """
        self.load_mock_wrsc_max()

        wfl_persisted_in_db = workflow_run.create_or_get_workflow(self.mock_wrsc_max)
        logger.info(wfl_persisted_in_db)
        self.assertEqual(Workflow.objects.count(), 1)

        # Try the second time. The workflow db lookup should be found the existing record.
        wfl_persisted_in_db2 = workflow_run.create_or_get_workflow(self.mock_wrsc_max)
        logger.info(wfl_persisted_in_db2)
        self.assertEqual(wfl_persisted_in_db.orcabus_id, wfl_persisted_in_db.orcabus_id)
        self.assertEqual(Workflow.objects.count(), 1)

    def test_create_or_get_workflow_run(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_create_or_get_workflow_run
        """
        self.load_mock_wrsc_max()

        wfl_persisted_in_db = workflow_run.create_or_get_workflow(self.mock_wrsc_max)

        wfr_persisted_in_db = workflow_run.create_or_get_workflow_run(self.mock_wrsc_max, wfl_persisted_in_db)
        logger.info(wfr_persisted_in_db)
        self.assertEqual(WorkflowRun.objects.count(), 1)

        # Try the second time. The workflow run db lookup should be found the existing record.
        wfr_persisted_in_db2 = workflow_run.create_or_get_workflow_run(self.mock_wrsc_max, wfl_persisted_in_db)
        logger.info(wfr_persisted_in_db2)
        self.assertEqual(wfr_persisted_in_db.orcabus_id, wfr_persisted_in_db2.orcabus_id)
        self.assertEqual(WorkflowRun.objects.count(), 1)

        # Verify related entities are created
        self.assertEqual(Workflow.objects.count(), 1)
        self.assertEqual(Library.objects.count(), 2)

    def test_create_or_get_workflow_run_without_library(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_create_or_get_workflow_run_without_library
        """
        self.load_mock_wrsc_min()

        wfl_persisted_in_db = workflow_run.create_or_get_workflow(self.mock_wrsc_min)

        wfr_persisted_in_db = workflow_run.create_or_get_workflow_run(self.mock_wrsc_min, wfl_persisted_in_db)
        logger.info(wfr_persisted_in_db)
        self.assertEqual(WorkflowRun.objects.count(), 1)

        # No libraries should be created
        self.assertEqual(Library.objects.count(), 0)

    def test_establish_workflow_run_libraries(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_establish_workflow_run_libraries
        """
        self.load_mock_wrsc_max()
        _ = WorkflowRunFactory()
        mock_wfr = WorkflowRun.objects.first()

        workflow_run.establish_workflow_run_libraries(self.mock_wrsc_max, mock_wfr)

        self.assertEqual(Library.objects.count(), 2)
        self.assertEqual(LibraryAssociation.objects.count(), 2)

    def test_establish_workflow_run_libraries_with_existing_library(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_establish_workflow_run_libraries_with_existing_library
        """
        self.load_mock_wrsc_max()
        _ = WorkflowRunFactory()
        mock_wfr = WorkflowRun.objects.first()

        l1 = Library.objects.create(
            library_id="L000001",
            orcabus_id="01J5M2J44HFJ9424G7074NKTGN"
        )
        l2 = Library.objects.create(
            library_id="L000002",
            orcabus_id="01J5M2JFE1JPYV62RYQEG99CP5"
        )
        self.assertEqual(Library.objects.count(), 2)
        logger.info(l1)
        logger.info(l2)

        self.assertEqual(LibraryAssociation.objects.count(), 0)

        workflow_run.establish_workflow_run_libraries(self.mock_wrsc_max, mock_wfr)

        self.assertEqual(LibraryAssociation.objects.count(), 2)

    def test_update_workflow_run_to_new_state(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_update_workflow_run_to_new_state
        """
        self.load_mock_wrsc_min()

        # First create wfr with min fixture DRAFT state
        wfl_persisted_in_db = workflow_run.create_or_get_workflow(self.mock_wrsc_min)
        wfr_persisted_in_db = workflow_run.create_or_get_workflow_run(self.mock_wrsc_min, wfl_persisted_in_db)

        success, state = workflow_run.update_workflow_run_to_new_state(self.mock_wrsc_min, wfr_persisted_in_db)
        logger.info(state)
        self.assertTrue(success)
        self.assertEqual(state.status, 'DRAFT')

        # Now try to update the state with max fixture
        self.load_mock_wrsc_max()
        success, state = workflow_run.update_workflow_run_to_new_state(self.mock_wrsc_max, wfr_persisted_in_db)
        logger.info(state)
        self.assertTrue(success)
        self.assertEqual(state.status, 'READY')

        # Verify related entities are created
        self.assertEqual(State.objects.count(), 2)
        self.assertEqual(Payload.objects.count(), 1)

    def test_map_workflow_run_new_state_to_wrsc(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_map_workflow_run_new_state_to_wrsc
        """
        self.load_mock_wrsc_max()
        wfl_persisted_in_db = workflow_run.create_or_get_workflow(self.mock_wrsc_max)
        wfr_persisted_in_db = workflow_run.create_or_get_workflow_run(self.mock_wrsc_max, wfl_persisted_in_db)

        anr = AnalysisRun.objects.create(
            analysis_run_name="wgts-dna"
        )
        wfr_persisted_in_db.analysis_run = anr
        wfr_persisted_in_db.save()

        success, new_state = workflow_run.update_workflow_run_to_new_state(self.mock_wrsc_max, wfr_persisted_in_db)

        out_wrsc = workflow_run.map_workflow_run_new_state_to_wrsc(wfr_persisted_in_db, new_state)
        logger.info(out_wrsc)

        validated_out_wrsc = WorkflowRunStateChange.model_validate(out_wrsc)

        self.assertIsNotNone(validated_out_wrsc)

    def test_get_wrsc_hash(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_get_wrsc_hash
        """
        self.load_mock_wrsc_min()

        hash_id = workflow_run.get_wrsc_hash(self.mock_wrsc_min)
        logger.info(hash_id)

        # Assert ID already exist in WRSC
        self.assertEqual(hash_id, "97534601940f17ebcfee02enotsecret")

        # Set ID to empty to force compute hash
        self.mock_wrsc_min.id = ""
        recomputed_hash_id = workflow_run.get_wrsc_hash(self.mock_wrsc_min)
        logger.info(recomputed_hash_id)
        self.assertEqual(recomputed_hash_id, "644ebbfd3c7819d80d9b6130c4717e02")
