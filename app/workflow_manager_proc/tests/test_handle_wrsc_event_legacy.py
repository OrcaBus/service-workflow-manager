import os
import uuid
from unittest import mock

from django.db.models import QuerySet

import workflow_manager.aws_event_bridge.executionservice.workflowrunstatechange as srv
from workflow_manager.models import WorkflowRun, Library, Workflow
from workflow_manager.models.workflow import ExecutionEngine, ValidationState
from workflow_manager_proc.domain.event import wrsc
from workflow_manager_proc.services.workflow_run_legacy import create_workflow_run
from workflow_manager_proc.tests.case import WorkflowManagerProcUnitTestCase, logger


class WorkflowSrvUnitTests(WorkflowManagerProcUnitTestCase):

    def setUp(self) -> None:
        self.env_mock = mock.patch.dict(os.environ, {"EVENT_BUS_NAME": "FooBus"})
        self.env_mock.start()
        super().setUp()

    def tearDown(self) -> None:
        self.env_mock.stop()
        super().tearDown()

    def test_create_wrsc_no_library(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run_legacy.WorkflowSrvUnitTests.test_create_wrsc_no_library
        """

        test_event_d = {
            "portalRunId": "202405012397gatc",
            "executionId": "icav2.id.12345",
            "timestamp": "2025-05-01T09:25:44Z",
            "status": "DRAFT",
            "workflowName": "ctTSO500",
            "workflowVersion": "4.2.7",
            "workflowRunName": "ctTSO500-L000002",
            "payload": {
                "version": "0.1.0",
                "data": {
                    "projectId": "bxxxxxxxx-dxxx-4xxxx-adcc-xxxxxxxxx",
                    "analysisId": "12345678-238c-4200-b632-d5dd8c8db94a",
                    "userReference": "540424_A01001_0193_BBBBMMDRX5_c754de_bd822f",
                    "timeCreated": "2024-05-01T10:11:35Z",
                    "timeModified": "2024-05-01T11:24:29Z",
                    "pipelineId": "bfffffff-cb27-4dfa-846e-acd6eb081aca",
                    "pipelineCode": "CTTSO500 v4_2_7",
                    "pipelineDescription": "This is an ctTSO500 workflow execution",
                    "pipelineUrn": "urn:ilmn:ica:pipeline:bfffffff-cb27-4dfa-846e-acd6eb081aca#CTTSO500_v4_2_7"
                }
            }
        }
        test_event: srv.WorkflowRunStateChange = srv.Marshaller.unmarshall(test_event_d, srv.WorkflowRunStateChange)

        logger.info("Test the created WRSC event...")
        result_wrsc: wrsc.WorkflowRunStateChange = create_workflow_run(test_event)
        logger.info(result_wrsc)
        self.assertIsNotNone(result_wrsc)
        self.assertEqual("ctTSO500-L000002", result_wrsc.workflowRunName)
        # We don't expect any library associations here!
        self.assertIsNone(result_wrsc.libraries)
        self.assertFalse(hasattr(result_wrsc, "linkedLibraries"))  # deprecated schema attribute name

        logger.info("Test the persisted DB record...")
        wfr_qs: QuerySet = WorkflowRun.objects.all()
        self.assertEqual(1, wfr_qs.count())
        db_wfr: WorkflowRun = wfr_qs.first()
        self.assertEqual("ctTSO500-L000002", db_wfr.workflow_run_name)
        # We don't expect any library associations here!
        self.assertEqual(0, db_wfr.libraries.count())

        # assert we can validate the emitting model
        self.assertIsNotNone(wrsc.WorkflowRunStateChange.model_validate(result_wrsc))

    def test_create_wrsc_no_payload(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run_legacy.WorkflowSrvUnitTests.test_create_wrsc_no_payload
        """

        test_event_d = {
            "portalRunId": "202405012397gatc",
            "executionId": "icav2.id.12345",
            "timestamp": "2025-05-01T09:25:44Z",
            "status": "DRAFT",
            "workflowName": "ctTSO500",
            "workflowVersion": "4.2.7",
            "workflowRunName": "ctTSO500-L000002"
        }
        test_event: srv.WorkflowRunStateChange = srv.Marshaller.unmarshall(test_event_d, srv.WorkflowRunStateChange)

        logger.info("Test the created WRSC event...")
        result_wrsc: wrsc.WorkflowRunStateChange = create_workflow_run(test_event)
        logger.info(result_wrsc)
        self.assertIsNotNone(result_wrsc)
        self.assertEqual("ctTSO500-L000002", result_wrsc.workflowRunName)
        # We don't expect any library associations here!
        self.assertIsNone(result_wrsc.libraries)
        self.assertIsNone(result_wrsc.payload)

        logger.info("Test the persisted DB record...")
        wfr_qs: QuerySet = WorkflowRun.objects.all()
        self.assertEqual(1, wfr_qs.count())
        db_wfr: WorkflowRun = wfr_qs.first()
        self.assertEqual("ctTSO500-L000002", db_wfr.workflow_run_name)
        # We don't expect any library associations here!
        self.assertEqual(0, db_wfr.libraries.count())

        # assert we can validate the emitting model
        self.assertIsNotNone(wrsc.WorkflowRunStateChange.model_validate(result_wrsc))

    def test_create_wrsc_library(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run_legacy.WorkflowSrvUnitTests.test_create_wrsc_library
        """
        # NOTE: orcabusId with and without prefix
        #       The DB records have to be generated without prefix
        #       The event records will be passed through as in the input
        library_ids = ["L000001", "L000002"]
        orcabus_ids = ["lib.01J5M2J44HFJ9424G7074NKTGN", "01J5M2JFE1JPYV62RYQEG99CP5"]
        lib_ids = [
            {
                "libraryId": library_ids[0],
                "orcabusId": orcabus_ids[0]
            },
            {
                "libraryId": library_ids[1],
                "orcabusId": orcabus_ids[1]
            }
        ]

        test_event_d = {
            "portalRunId": "202405012397gatc",
            "executionId": "icav2.id.12345",
            "timestamp": "2025-05-01T09:25:44Z",
            "status": "DRAFT",
            "workflowName": "ctTSO500",
            "workflowVersion": "4.2.7",
            "workflowRunName": "ctTSO500-L000002",
            "linkedLibraries": lib_ids,
            "payload": {
                "version": "0.1.0",
                "data": {
                    "projectId": "bxxxxxxxx-dxxx-4xxxx-adcc-xxxxxxxxx",
                    "analysisId": "12345678-238c-4200-b632-d5dd8c8db94a",
                    "userReference": "540424_A01001_0193_BBBBMMDRX5_c754de_bd822f",
                    "timeCreated": "2024-05-01T10:11:35Z",
                    "timeModified": "2024-05-01T11:24:29Z",
                    "pipelineId": "bfffffff-cb27-4dfa-846e-acd6eb081aca",
                    "pipelineCode": "CTTSO500 v4_2_7",
                    "pipelineDescription": "This is an ctTSO500 workflow execution",
                    "pipelineUrn": "urn:ilmn:ica:pipeline:bfffffff-cb27-4dfa-846e-acd6eb081aca#CTTSO500_v4_2_7"
                }
            }
        }
        test_event: srv.WorkflowRunStateChange = srv.Marshaller.unmarshall(test_event_d, srv.WorkflowRunStateChange)

        logger.info("Test the created WRSC event...")
        result_wrsc: wrsc.WorkflowRunStateChange = create_workflow_run(test_event)
        logger.info(result_wrsc)

        # ensure that all library records have been created as proper ULIDs (without prefixes)
        db_libs = Library.objects.all()
        for l in db_libs:
            self.assertTrue(len(l.orcabus_id), 26)

        self.assertIsNotNone(result_wrsc)
        self.assertEqual("ctTSO500-L000002", result_wrsc.workflowRunName)
        # We do expect 2 library associations here!
        self.assertIsNotNone(result_wrsc.libraries)
        self.assertEqual(2, len(result_wrsc.libraries))
        for lib in result_wrsc.libraries:
            self.assertTrue(lib.libraryId in library_ids)
            self.assertTrue(lib.orcabusId in orcabus_ids)

        logger.info("Test the persisted DB record...")
        wfr_qs: QuerySet = WorkflowRun.objects.all()
        self.assertEqual(1, wfr_qs.count())
        db_wfr: WorkflowRun = wfr_qs.first()
        self.assertEqual("ctTSO500-L000002", db_wfr.workflow_run_name)
        # We do expect 2 library associations here!
        self.assertEqual(2, db_wfr.libraries.count())
        for lib in db_wfr.libraries.all():
            self.assertTrue(lib.library_id in library_ids)

        # assert we can validate the emitting model
        self.assertIsNotNone(wrsc.WorkflowRunStateChange.model_validate(result_wrsc))

    def test_create_wrsc_library_exists(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run_legacy.WorkflowSrvUnitTests.test_create_wrsc_library_exists
        """

        # NOTE: orcabusId with and without prefix
        #       The DB records have to be generated without prefix
        #       The event records will be passed through as in the input
        library_ids = ["L000001", "L000002"]
        orcabus_ids = ["lib.01J5M2J44HFJ9424G7074NKTGN", "01J5M2JFE1JPYV62RYQEG99CP5"]
        lib_ids = [
            {
                "libraryId": library_ids[0],
                "orcabusId": orcabus_ids[0]
            },
            {
                "libraryId": library_ids[1],
                "orcabusId": orcabus_ids[1]
            }
        ]
        for lib_id in lib_ids:
            Library.objects.create(
                library_id=lib_id["libraryId"],
                orcabus_id=lib_id["orcabusId"]
            )

        # ensure that all library records have been created as proper ULIDs (without prefixes)
        db_libs = Library.objects.all()
        for l in db_libs:
            self.assertTrue(len(l.orcabus_id), 26)

        test_event_d = {
            "portalRunId": "202405012397gatc",
            "executionId": "icav2.id.12345",
            "timestamp": "2025-05-01T09:25:44Z",
            "status": "DRAFT",
            "workflowName": "ctTSO500",
            "workflowVersion": "4.2.7",
            "workflowRunName": "ctTSO500-L000002",
            "linkedLibraries": lib_ids,
            "payload": {
                "version": "0.1.0",
                "data": {
                    "projectId": "bxxxxxxxx-dxxx-4xxxx-adcc-xxxxxxxxx",
                    "analysisId": "12345678-238c-4200-b632-d5dd8c8db94a",
                    "userReference": "540424_A01001_0193_BBBBMMDRX5_c754de_bd822f",
                    "timeCreated": "2024-05-01T10:11:35Z",
                    "timeModified": "2024-05-01T11:24:29Z",
                    "pipelineId": "bfffffff-cb27-4dfa-846e-acd6eb081aca",
                    "pipelineCode": "CTTSO500 v4_2_7",
                    "pipelineDescription": "This is an ctTSO500 workflow execution",
                    "pipelineUrn": "urn:ilmn:ica:pipeline:bfffffff-cb27-4dfa-846e-acd6eb081aca#CTTSO500_v4_2_7"
                }
            }
        }
        test_event: srv.WorkflowRunStateChange = srv.Marshaller.unmarshall(test_event_d, srv.WorkflowRunStateChange)

        logger.info("Test the created WRSC event...")
        result_wrsc: wrsc.WorkflowRunStateChange = create_workflow_run(test_event)
        logger.info(result_wrsc)
        self.assertIsNotNone(result_wrsc)
        self.assertEqual("ctTSO500-L000002", result_wrsc.workflowRunName)
        # We do expect 2 library associations here!
        self.assertIsNotNone(result_wrsc.libraries)
        self.assertEqual(2, len(result_wrsc.libraries))
        for lib in result_wrsc.libraries:
            self.assertTrue(lib.libraryId in library_ids)
            self.assertTrue(lib.orcabusId in orcabus_ids)

        logger.info("Test the persisted DB record...")
        wfr_qs: QuerySet = WorkflowRun.objects.all()
        self.assertEqual(1, wfr_qs.count())
        db_wfr: WorkflowRun = wfr_qs.first()
        self.assertEqual("ctTSO500-L000002", db_wfr.workflow_run_name)
        # We do expect 2 library associations here!
        self.assertEqual(2, db_wfr.libraries.count())
        for lib in db_wfr.libraries.all():
            self.assertTrue(lib.library_id in library_ids)

        # assert we can validate the emitting model
        self.assertIsNotNone(wrsc.WorkflowRunStateChange.model_validate(result_wrsc))

    def test_create_workflow_run_legacy_dynamic_workflow_creation_behaviour(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run_legacy.WorkflowSrvUnitTests.test_create_workflow_run_legacy_dynamic_workflow_creation_behaviour
        """
        self.load_mock_wrsc_legacy()

        # Pre Condition
        self.assertEqual(0, Workflow.objects.count())

        mock_wrsc_event_with_envelope = srv.Marshaller.unmarshall(self.event, srv.AWSEvent)

        create_workflow_run(mock_wrsc_event_with_envelope.detail)

        # Post Condition
        self.assertEqual(Workflow.objects.count(), 1)
        # Assert that the legacy values are used in the new schema column fields
        persisted_wfl: Workflow = Workflow.objects.first()
        self.assertEqual(persisted_wfl.code_version, "0.0.0")
        self.assertEqual(persisted_wfl.execution_engine, "Unknown")
        self.assertEqual(persisted_wfl.execution_engine_pipeline_id, "Unknown")
        self.assertEqual(persisted_wfl.validation_state, "VALIDATED")

    def test_create_workflow_run_legacy_dynamic_workflow_get_behaviour(self):
        """
        python manage.py test workflow_manager_proc.tests.test_workflow_run_legacy.WorkflowSrvUnitTests.test_create_workflow_run_legacy_dynamic_workflow_get_behaviour
        """
        self.load_mock_wrsc_legacy()

        # Legacy dynamic workflow creation behaviour
        existing_workflow_legacy = Workflow.objects.create(
            name=self.event['detail']['workflowName'],
            version=self.event['detail']['workflowVersion'],
            execution_engine="Unknown",
            execution_engine_pipeline_id="Unknown",
            validation_state=ValidationState.VALIDATED.value,
        )

        # New deterministic workflow creation behaviour (via API)
        _ = Workflow.objects.create(
            name=self.event['detail']['workflowName'],
            version=self.event['detail']['workflowVersion'],
            code_version="85ce3d-dev",
            execution_engine=ExecutionEngine.ICA.value,
            execution_engine_pipeline_id=str(uuid.uuid4()),
            validation_state=ValidationState.UNVALIDATED.value,
        )

        # Pre Condition
        self.assertEqual(2, Workflow.objects.count())

        mock_wrsc_event_with_envelope = srv.Marshaller.unmarshall(self.event, srv.AWSEvent)

        out_wrsc = create_workflow_run(mock_wrsc_event_with_envelope.detail)

        # Post Condition
        # Assert that no new Workflow have been created. Database get query should found existing legacy record.
        self.assertEqual(Workflow.objects.count(), 2)
        # Assert that the legacy values are used in the new schema column fields
        self.assertEqual(out_wrsc.workflow.name, existing_workflow_legacy.name)
        self.assertEqual(out_wrsc.workflow.version, existing_workflow_legacy.version)
        self.assertEqual(out_wrsc.workflow.codeVersion, existing_workflow_legacy.code_version)
        self.assertEqual(out_wrsc.workflow.executionEngine, existing_workflow_legacy.execution_engine)
        self.assertEqual(out_wrsc.workflow.executionEnginePipelineId,
                         existing_workflow_legacy.execution_engine_pipeline_id)
        self.assertEqual(out_wrsc.workflow.validationState, existing_workflow_legacy.validation_state)
