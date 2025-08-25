import os
from unittest import mock

from mockito import when, unstub

from workflow_manager.models import Workflow, WorkflowRun, Library, LibraryAssociation, State, Payload, AnalysisRun, \
    Readset, RunContext
from workflow_manager.models.run_context import RunContextUseCase
from workflow_manager.tests.factories import WorkflowRunFactory
from workflow_manager_proc.domain.event import wrsc
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
        self.load_mock_wru_min()
        out_wrsc = workflow_run.create_workflow_run(self.mock_wru_min)
        self.assertIsNotNone(out_wrsc)
        self.assertEqual(Workflow.objects.count(), 1)
        self.assertEqual(WorkflowRun.objects.count(), 1)
        self.assertEqual(State.objects.count(), 1)
        self.assertEqual(Payload.objects.count(), 0)

    def test_create_workflow_run_state_has_not_been_updated(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_create_workflow_run_state_has_not_been_updated
        """
        self.load_mock_wru_min()
        when(workflow_run).update_workflow_run_to_new_state(...).thenReturn((False, "DOES_NOT_MATTER"))
        out_wrsc = workflow_run.create_workflow_run(self.mock_wru_min)
        self.assertIsNone(out_wrsc)
        self.assertEqual(Workflow.objects.count(), 1)
        self.assertEqual(WorkflowRun.objects.count(), 1)
        self.assertEqual(State.objects.count(), 0)
        self.assertEqual(Payload.objects.count(), 0)

    def test_create_or_get_workflow(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_create_or_get_workflow
        """
        self.load_mock_wru_max()

        wfl_persisted_in_db = workflow_run.create_or_get_workflow(self.mock_wru_max)
        logger.info(wfl_persisted_in_db)
        self.assertEqual(Workflow.objects.count(), 1)

        # Try the second time. The workflow db lookup should be found the existing record.
        wfl_persisted_in_db2 = workflow_run.create_or_get_workflow(self.mock_wru_max)
        logger.info(wfl_persisted_in_db2)
        self.assertEqual(wfl_persisted_in_db.orcabus_id, wfl_persisted_in_db.orcabus_id)
        self.assertEqual(Workflow.objects.count(), 1)

    def test_create_or_get_workflow_run(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_create_or_get_workflow_run
        """
        self.load_mock_wru_max()

        wfl_persisted_in_db = workflow_run.create_or_get_workflow(self.mock_wru_max)

        wfr_persisted_in_db = workflow_run.create_or_get_workflow_run(self.mock_wru_max, wfl_persisted_in_db)
        logger.info(wfr_persisted_in_db)
        self.assertEqual(WorkflowRun.objects.count(), 1)

        # Try the second time. The workflow run db lookup should be found the existing record.
        wfr_persisted_in_db2 = workflow_run.create_or_get_workflow_run(self.mock_wru_max, wfl_persisted_in_db)
        logger.info(wfr_persisted_in_db2)
        self.assertEqual(wfr_persisted_in_db.orcabus_id, wfr_persisted_in_db2.orcabus_id)
        self.assertEqual(WorkflowRun.objects.count(), 1)

        # Verify related entities are created
        self.assertEqual(Workflow.objects.count(), 1)
        self.assertEqual(Library.objects.count(), 2)

    def test_establish_workflow_run_libraries(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_establish_workflow_run_libraries
        """
        self.load_mock_wru_max()
        _ = WorkflowRunFactory()
        mock_wfr = WorkflowRun.objects.first()

        workflow_run.establish_workflow_run_libraries(self.mock_wru_max, mock_wfr)

        logger.info(mock_wfr)

        self.assertEqual(Library.objects.count(), 2)
        self.assertEqual(LibraryAssociation.objects.count(), 2)
        self.assertEqual(Readset.objects.count(), 4)

        logger.info(Library.objects.values_list())
        logger.info(Readset.objects.values_list())

    def test_establish_workflow_run_libraries_with_existing_library(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_establish_workflow_run_libraries_with_existing_library
        """
        self.load_mock_wru_max()
        _ = WorkflowRunFactory()
        mock_wfr: WorkflowRun = WorkflowRun.objects.first()

        # add pre-existing libraries
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

        # add pre-existing readsets
        rs1 = Readset.objects.create(
            orcabus_id="READSET123456789ABCDEFGHJK",
            rgid="AAGCAGTC+ACGCCAAC.1.990101_A00130_0999_BH7TVMDSX7",
            library_id=l1.library_id,
            library_orcabus_id=l1.orcabus_id,
        )
        rs2 = Readset.objects.create(
            orcabus_id="READSET234567891ABCDEFGHJK",
            rgid="AAGCAGTC+ACGCCAAC.2.990101_A00130_0999_BH7TVMDSX7",
            library_id=l1.library_id,
            library_orcabus_id=l1.orcabus_id,
        )
        rs3 = Readset.objects.create(
            orcabus_id="READSET345678912ABCDEFGHJK",
            rgid="CCGCAGTC+TCGCCAAC.1.990101_A00130_0999_BH7TVMDSX7",
            library_id=l2.library_id,
            library_orcabus_id=l2.orcabus_id,
        )
        rs4 = Readset.objects.create(
            orcabus_id="READSET456789123ABCDEFGHJK",
            rgid="CCGCAGTC+TCGCCAAC.2.990101_A00130_0999_BH7TVMDSX7",
            library_id=l2.library_id,
            library_orcabus_id=l2.orcabus_id,
        )
        logger.info(rs1)
        logger.info(rs2)
        logger.info(rs3)
        logger.info(rs4)

        self.assertEqual(LibraryAssociation.objects.count(), 0)
        self.assertEqual(Readset.objects.count(), 4)

        workflow_run.establish_workflow_run_libraries(self.mock_wru_max, mock_wfr)

        self.assertEqual(LibraryAssociation.objects.count(), 2)
        self.assertEqual(Readset.objects.count(), 4)

        logger.info(mock_wfr.readsets.values_list())
        self.assertEqual(mock_wfr.readsets.values_list().count(), 4)

    def test_establish_workflow_run_contexts(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_establish_workflow_run_contexts
        """
        self.load_mock_wru_max()
        _ = WorkflowRunFactory()
        mock_wfr = WorkflowRun.objects.first()

        self.assertEqual(RunContext.objects.count(), 0)

        workflow_run.establish_workflow_run_contexts(self.mock_wru_max, mock_wfr)

        logger.info(mock_wfr)
        logger.info(RunContext.objects.values_list())

        self.assertEqual(RunContext.objects.count(), 2)

    def test_establish_workflow_run_contexts_with_existing(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_establish_workflow_run_contexts_with_existing
        """
        self.load_mock_wru_max()
        _ = WorkflowRunFactory()
        mock_wfr = WorkflowRun.objects.first()

        # add pre-existing RunContext
        ctx1 = RunContext.objects.create(
            name="clinical",
            usecase=RunContextUseCase.COMPUTE.value,
        )
        ctx2 = RunContext.objects.create(
            name="clinical",
            usecase=RunContextUseCase.STORAGE.value,
        )
        self.assertEqual(RunContext.objects.count(), 2)
        logger.info(ctx1)
        logger.info(ctx2)

        workflow_run.establish_workflow_run_contexts(self.mock_wru_max, mock_wfr)

        logger.info(mock_wfr)
        logger.info(RunContext.objects.values_list())

        self.assertEqual(RunContext.objects.count(), 2)

    def test_update_workflow_run_to_new_state(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_update_workflow_run_to_new_state
        """
        self.load_mock_wru_min()

        # First create wfr with min fixture DRAFT state
        wfl_persisted_in_db = workflow_run.create_or_get_workflow(self.mock_wru_min)
        wfr_persisted_in_db = workflow_run.create_or_get_workflow_run(self.mock_wru_min, wfl_persisted_in_db)

        success, state = workflow_run.update_workflow_run_to_new_state(self.mock_wru_min, wfr_persisted_in_db)
        logger.info(state)
        self.assertTrue(success)
        self.assertEqual(state.status, 'DRAFT')

        # Now try to update the state with max fixture
        self.load_mock_wru_max()
        self.mock_wru_max.timestamp = None  # reset WRU fixture timestamp so that it can advance to next state
        success, state = workflow_run.update_workflow_run_to_new_state(self.mock_wru_max, wfr_persisted_in_db)
        logger.info(state)
        self.assertTrue(success)
        self.assertEqual(state.status, 'READY')

        # Verify related entities are created
        self.assertEqual(State.objects.count(), 2)
        self.assertEqual(Payload.objects.count(), 1)

    def test_update_workflow_run_to_new_state_with_ref_id(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_update_workflow_run_to_new_state_with_ref_id
        """
        self.load_mock_wru_max()

        # First create wfr with min fixture DRAFT state
        wfl_persisted_in_db = workflow_run.create_or_get_workflow(self.mock_wru_max)
        wfr_persisted_in_db = workflow_run.create_or_get_workflow_run(self.mock_wru_max, wfl_persisted_in_db)

        success, state = workflow_run.update_workflow_run_to_new_state(self.mock_wru_max, wfr_persisted_in_db)
        logger.info(state)

        self.assertTrue(success)
        self.assertEqual(state.status, 'READY')

        # Verify related entities are created
        self.assertEqual(State.objects.count(), 1)
        self.assertEqual(Payload.objects.count(), 1)

        self.assertEqual(Payload.objects.first().payload_ref_id, '99995678-238c-4200-b632-d5dd8c8db94a')

    def test_update_workflow_run_to_new_state_without_ref_id(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_update_workflow_run_to_new_state_without_ref_id
        """
        self.load_mock_wru_max()

        # Nullify payload refId
        self.mock_wru_max.payload.refId = None

        # First create wfr with min fixture DRAFT state
        wfl_persisted_in_db = workflow_run.create_or_get_workflow(self.mock_wru_max)
        wfr_persisted_in_db = workflow_run.create_or_get_workflow_run(self.mock_wru_max, wfl_persisted_in_db)

        success, state = workflow_run.update_workflow_run_to_new_state(self.mock_wru_max, wfr_persisted_in_db)
        logger.info(state)

        self.assertTrue(success)
        self.assertEqual(state.status, 'READY')

        # Verify related entities are created
        self.assertEqual(State.objects.count(), 1)
        self.assertEqual(Payload.objects.count(), 1)

        logger.info(Payload.objects.first().payload_ref_id)

        self.assertNotEqual(Payload.objects.first().payload_ref_id, '99995678-238c-4200-b632-d5dd8c8db94a')

    def test_map_workflow_run_new_state_to_wrsc(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_map_workflow_run_new_state_to_wrsc
        """
        self.load_mock_wru_max()
        wfl_persisted_in_db = workflow_run.create_or_get_workflow(self.mock_wru_max)
        wfr_persisted_in_db = workflow_run.create_or_get_workflow_run(self.mock_wru_max, wfl_persisted_in_db)

        anr = AnalysisRun.objects.create(
            analysis_run_name="wgts-dna"
        )
        wfr_persisted_in_db.analysis_run = anr
        wfr_persisted_in_db.save()

        success, new_state = workflow_run.update_workflow_run_to_new_state(self.mock_wru_max, wfr_persisted_in_db)

        out_wrsc = workflow_run.map_workflow_run_new_state_to_wrsc(wfr_persisted_in_db, new_state)
        logger.info(out_wrsc.model_dump_json())

        validated_out_wrsc = wrsc.WorkflowRunStateChange.model_validate(out_wrsc)

        self.assertIsNotNone(validated_out_wrsc)

    def test_get_wrsc_hash(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_get_wrsc_hash
        """
        self.load_mock_wru_max()

        libs = []
        for lib in self.mock_wru_max.libraries:
            wrsc_l = wrsc.Library(
                libraryId=lib.libraryId,
                orcabusId=lib.orcabusId,
            )
            rs_list = []
            for rs in lib.readsets:
                wrsc_rs = wrsc.Readset(
                    orcabusId=rs.orcabusId,
                    rgid=rs.rgid,
                )
                rs_list.append(wrsc_rs)
            wrsc_l.readsets = rs_list
            libs.append(wrsc_l)

        mock_wrsc = wrsc.WorkflowRunStateChange(
            id=self.mock_wru_max.id,
            version=self.mock_wru_max.version,
            timestamp=self.mock_wru_max.timestamp,
            orcabusId=self.mock_wru_max.orcabusId,
            portalRunId=self.mock_wru_max.portalRunId,
            workflowRunName=self.mock_wru_max.workflowRunName,
            workflow=wrsc.Workflow(
                orcabusId=self.mock_wru_max.workflow.orcabusId,
                name=self.mock_wru_max.workflow.name,
                version=self.mock_wru_max.workflow.version,
                executionEngine=self.mock_wru_max.workflow.executionEngine,
            ),
            analysisRun=wrsc.AnalysisRun(
                orcabusId=self.mock_wru_max.analysisRun.orcabusId,
                name=self.mock_wru_max.analysisRun.name,
            ),
            libraries=libs,
            status=self.mock_wru_max.status,
            payload=wrsc.Payload(
                orcabusId="pld.01J5M2JFE1JPYV62RYQEG99PLD",
                refId=self.mock_wru_max.payload.refId,
                version=self.mock_wru_max.payload.version,
                data=self.mock_wru_max.payload.data,
            ),
            computeEnv=self.mock_wru_max.computeEnv,
            storageEnv=self.mock_wru_max.storageEnv,
        )

        hash_id = workflow_run.get_wrsc_hash(mock_wrsc)
        logger.info(hash_id)

        # Assert ID already exist in WRSC
        self.assertEqual(hash_id, "97534601940f17ebcfee02enotsecret")

        # Set ID to empty to force compute hash
        mock_wrsc.id = ""
        recomputed_hash_id = workflow_run.get_wrsc_hash(mock_wrsc)
        logger.info(recomputed_hash_id)
        self.assertEqual(recomputed_hash_id, "c245d06133737ec8c080a2792fd54e2a")
