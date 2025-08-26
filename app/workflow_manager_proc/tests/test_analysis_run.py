import datetime
import os
import time
from unittest import mock

from django.utils.timezone import make_aware

from workflow_manager.models import Library, Status, AnalysisContext, AnalysisRunState, RunContext
from workflow_manager.models.analysis import Analysis
from workflow_manager.models.analysis_context import AnalysisContextUseCase
from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager_proc.domain.event import arsc
from workflow_manager_proc.services.analysis_run import (
    _create_analysis_run,
    _finalise_analysis_run,
    _map_analysis_run_to_arsc,
    get_arsc_hash
)
from workflow_manager_proc.tests.case import WorkflowManagerProcUnitTestCase, logger

ANALYSIS_1_NAME = "TestAnalysis1"
ANALYSIS_1_OID = "ana.76J5N2J83RED7387G9374NGDBA"


class AnalysisRunUnitTests(WorkflowManagerProcUnitTestCase):
    fixtures = ['./workflow_manager_proc/tests/fixtures/aru_test_fixtures.json', ]

    def setUp(self) -> None:
        self.env_mock = mock.patch.dict(os.environ, {"EVENT_BUS_NAME": "FooBus"})
        self.env_mock.start()
        super().setUp()

    def tearDown(self) -> None:
        self.env_mock.stop()
        # self.clean_base_entities()
        super().tearDown()

    def test_aru_draft_min(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_aru_draft_min
        """
        self.load_mock_aru_draft_min()
        aru_analysis_run = self.mock_aru_draft_min
        self.assertIsNotNone(aru_analysis_run)

        logger.info("Testing DB record creation from event...")
        db_analysis_run = _create_analysis_run(aru_analysis_run)
        self.assertIsNotNone(db_analysis_run)
        self.assertEqual(db_analysis_run.analysis.analysis_name, "WGS")
        self.assertEqual(db_analysis_run.analysis.analysis_version, "1.0")
        self.assertEqual(db_analysis_run.analysis_run_name, "TestAnalysisRunName_1")
        self.assertEqual(db_analysis_run.get_latest_state().status, Status.DRAFT.convention)
        self.assertEqual(db_analysis_run.contexts.count(), 0)
        self.assertEqual(AnalysisRun.objects.count(), 1)

        logger.info("ARSC event creation from DB record...")
        arsc_event = _map_analysis_run_to_arsc(db_analysis_run)
        self.assertIsNotNone(arsc_event)
        # check whether the hash id was set properly
        test_id = get_arsc_hash(arsc_event)
        self.assertEqual(test_id, arsc_event.id)
        # NOTE: We cannot directly test the hash id as the OrcaBus ID of the generated AnalysisRun
        #       will constantly change with every new generation. Therefore we overwrite it with a
        #       fixed ID to make the generated hash stable. This allows testing of the rest of the
        #       elements that make up the hash.
        # NOTE: We also have to reset the has id assigned above to allow it to be recalculated
        arsc_event.orcabusId = "anr.11223344556677889900TEST01"
        arsc_event.id = None  # reset the previously assigned hash id
        testable_hash_id = get_arsc_hash(arsc_event)
        self.assertEqual(testable_hash_id, "21547fb4fe7e4ca2454eddd656065613")

    def test_aru_draft_max(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_aru_draft_max
        """
        self.load_mock_aru_draft_max()
        aru_analysis_run = self.mock_aru_draft_max
        self.assertIsNotNone(aru_analysis_run)

        logger.info("Testing DB record creation from event...")
        db_analysis_run = _create_analysis_run(aru_analysis_run)
        self.assertIsNotNone(db_analysis_run)
        self.assertEqual(db_analysis_run.analysis.analysis_name, "WGS")
        self.assertEqual(db_analysis_run.analysis.analysis_version, "2.0")
        self.assertEqual(db_analysis_run.analysis_run_name, "TestAnalysisRunName_1")
        self.assertEqual(db_analysis_run.get_latest_state().status, Status.DRAFT.convention)
        self.assertEqual(db_analysis_run.contexts.count(), 2)
        self.assertEqual(AnalysisRun.objects.count(), 1)

        logger.info("ARSC event creation from DB record...")
        arsc_event = _map_analysis_run_to_arsc(db_analysis_run)
        self.assertIsNotNone(arsc_event)
        # check whether the hash id was set properly
        test_id = get_arsc_hash(arsc_event)
        self.assertEqual(test_id, arsc_event.id)
        # NOTE: We cannot directly test the hash id as the OrcaBus ID of the generated AnalysisRun
        #       will constantly change with every new generation. Therefore we overwrite it with a
        #       fixed ID to make the generated hash stable. This allows testing of the rest of the
        #       elements that make up the hash.
        # NOTE: We also have to reset the has id assigned above to allow it to be recalculated
        arsc_event.orcabusId = "anr.11223344556677889900TEST01"
        arsc_event.id = None  # reset the previously assigned hash id
        testable_hash_id = get_arsc_hash(arsc_event)
        self.assertEqual(testable_hash_id, "4676030bea0c4d172f34bc4be39237ef")

    def test_aru_ready_max(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_aru_ready_max
        """

        # Now run the READY event
        self.load_mock_aru_ready_max()
        aru_analysis_run = self.mock_aru_ready_max
        self.assertIsNotNone(aru_analysis_run)

        logger.info("Testing DB record creation from event...")
        self.assertRaises(AnalysisRun.DoesNotExist, _finalise_analysis_run, aru_analysis_run)

    def test_aru_draft_to_ready_1(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_aru_draft_to_ready_1

        Test the AnalysisRun creation via ARU DRAFT event and finalisation via following ARU READY event.
        This should test the common case of AnalysisRun creation by external execution services.
        """
        # Run the DRAFT event
        self.load_mock_aru_draft_max()
        aru_analysis_run = self.mock_aru_draft_max
        self.assertIsNotNone(aru_analysis_run)
        db_analysis_run_draft = _create_analysis_run(aru_analysis_run)
        self.assertEqual(AnalysisRun.objects.count(), 1)
        self.assertEqual(db_analysis_run_draft.get_latest_state().status, Status.DRAFT.convention)
        logger.info("DRAFT event handling finished.")

        # Now run the READY event
        self.load_mock_aru_ready_max()
        aru_analysis_run = self.mock_aru_ready_max
        self.assertIsNotNone(aru_analysis_run)
        # Now set the OrcaBus ID that was assigned to the DRAFT, so they match
        aru_analysis_run.orcabusId = db_analysis_run_draft.orcabus_id

        logger.info("Testing DB record creation from event...")
        db_analysis_run = _finalise_analysis_run(aru_analysis_run)
        self.assertIsNotNone(db_analysis_run)
        self.assertEqual(db_analysis_run.analysis.analysis_name, "WGS")
        self.assertEqual(db_analysis_run.analysis.analysis_version, "2.0")
        self.assertEqual(db_analysis_run.analysis_run_name, "TestAnalysisRunName_1")
        self.assertEqual(db_analysis_run.get_latest_state().status, Status.READY.convention)
        self.assertEqual(db_analysis_run.contexts.count(), 2)
        self.assertEqual(AnalysisRun.objects.count(), 1)

        logger.info("ARSC event creation from DB record...")
        arsc_event = _map_analysis_run_to_arsc(db_analysis_run)
        self.assertIsNotNone(arsc_event)
        # check whether the hash id was set properly
        test_id = get_arsc_hash(arsc_event)
        self.assertEqual(test_id, arsc_event.id)
        # NOTE: We cannot directly test the hash id as the OrcaBus ID of the generated AnalysisRun
        #       will constantly change with every new generation. Therefore we overwrite it with a
        #       fixed ID to make the generated hash stable. This allows testing of the rest of the
        #       elements that make up the hash.
        # NOTE: We also have to reset the has id assigned above to allow it to be recalculated
        arsc_event.orcabusId = "anr.11223344556677889900TEST01"
        arsc_event.id = None  # reset the previously assigned hash id
        testable_hash_id = get_arsc_hash(arsc_event)
        self.assertEqual(testable_hash_id, "460bdbf4a9ca9bec77c5991b3509a15a")

        # run some spot checks
        self.assertEqual(db_analysis_run_draft.analysis, db_analysis_run.analysis)
        self.assertEqual(db_analysis_run_draft.analysis_run_name, db_analysis_run.analysis_run_name)
        self.assertEqual(db_analysis_run_draft.orcabus_id, db_analysis_run.orcabus_id)

    def test_aru_draft_to_ready_2(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_aru_draft_to_ready_2

        Test the AnalysisRun creation via ARU DRAFT event and finalisation via following ARU READY event.
        This should test the common case of AnalysisRun creation by external execution services.
        """
        # Assume an AnalysisRun has already been created and finalised
        self.test_aru_draft_to_ready_1()

        # then receive repeated ARU event for the same AnalysisRun
        # create the AnalysisRun with the repeated ARU event
        with self.assertRaises(Exception) as err:
            _create_analysis_run(self.mock_aru_draft_max)
        self.assertEqual(str(err.exception), 'AnalysisRun record already exists!')
        logger.info(str(err.exception))

    def test_aru_draft_to_ready_3(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_aru_draft_to_ready_3

        Test the AnalysisRun creation via ARU DRAFT event and finalisation via following ARU READY event.
        This should test the common case of AnalysisRun creation by external execution services.
        """
        # Assume an AnalysisRun has already been created and finalised
        self.test_aru_draft_to_ready_1()

        # then receive a new ARU event for the same AnalysisRun
        # create the AnalysisRun with the repeated ARU event

        # We expect an error since we call a method meant to handle DRAFT events
        # with an event that has a READY status
        with self.assertRaises(Exception) as err:
            _create_analysis_run(self.mock_aru_ready_max)
        self.assertEqual(str(err.exception), 'AnalysisRunUpdate: Unexpected state!')
        logger.info(str(err.exception))

    def test_aru_draft_to_ready_4(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_aru_draft_to_ready_4

        Test the handling of a duplicated READY event, e.g. after it has already been processed
        """
        # Assume an AnalysisRun has already been created and finalised
        self.test_aru_draft_to_ready_1()

        # then receive a new ARU READY event for the same AnalysisRun
        # create the AnalysisRun with the repeated ARU event

        # We expect an error since we call a method meant to handle DRAFT events
        # with an event that has a READY status
        with self.assertRaises(Exception) as err:
            _finalise_analysis_run(self.mock_aru_ready_max)
        self.assertEqual(str(err.exception), 'Cannot finalise record that is no in DRAFT state!')
        logger.info(str(err.exception))

    def test_get_arsc_hash(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_get_arsc_hash
        """

        test_analysis = arsc.Analysis(
            orcabusId="SOME9ARSC9ANALYSIS9ID12345",
            name="TestAnalysis1",
            version="0.0.1",
        )
        test_arsc = arsc.AnalysisRunStateChange(
            id="",
            version="0.0.1",
            timestamp=datetime.datetime.strptime("01/05/2025 6:00", "%m/%d/%Y %H:%M"),
            orcabusId="SOME9ARSC9ANALYSISRUN9ID12345",
            analysisRunName="testAnalysisRunName",
            analysis=test_analysis,
            computeEnv="ENV1",
            storageEnv="ENV2",
            status="TESTING",
            libraries=[
                arsc.Library(
                    orcabusId="SOME9ARSC9LIBRARY9ID12345",
                    libraryId="L9900999"
                )
            ]
        )
        hash_0 = get_arsc_hash(test_arsc)
        time.sleep(2)
        hash_x = get_arsc_hash(test_arsc)
        assert hash_0 == hash_x, "Hash isn't the same!"

        # Change some data and expect a different hash
        test_arsc.status = "TESTING2"
        hash_x = get_arsc_hash(test_arsc)
        assert hash_0 != hash_x, "Hash is the same!"

        # Change back and expect the hash to match again
        test_arsc.status = "TESTING"
        hash_x = get_arsc_hash(test_arsc)
        assert hash_0 == hash_x, "Hash isn't that same!"

        # Change compute env and expect a different hash
        test_arsc.computeEnv = "Changed"
        hash_x = get_arsc_hash(test_arsc)
        assert hash_0 != hash_x, "Hash is the same!"

        # Change storage env and expect a different hash
        test_arsc.storageEnv = "Changed"
        hash_x = get_arsc_hash(test_arsc)
        assert hash_0 != hash_x, "Hash is the same!"

        # Change analysis run name and expect a different hash
        test_arsc.analysisRunName = "Changed"
        hash_x = get_arsc_hash(test_arsc)
        assert hash_0 != hash_x, "Hash is the same!"

        # Change version and expect a different hash
        test_arsc.version = "99.99.99"
        hash_x = get_arsc_hash(test_arsc)
        assert hash_0 != hash_x, "Hash is the same!"

        # Change oid and expect a different hash
        test_arsc.orcabusId = "CHANGED9ID12345"
        hash_x = get_arsc_hash(test_arsc)
        assert hash_0 != hash_x, "Hash is the same!"

        # Change analysis oid and expect a different hash
        test_arsc.analysis.orcabusId = "CHANGED9ID12345"
        hash_x = get_arsc_hash(test_arsc)
        assert hash_0 != hash_x, "Hash is the same!"

        # Change timestamp and expect a different hash
        test_arsc.timestamp = datetime.datetime.strptime("01/05/2025 6:01", "%m/%d/%Y %H:%M")
        hash_x = get_arsc_hash(test_arsc)
        assert hash_0 != hash_x, "Hash is the same!"

        # add library and expect a different hash
        lib_1 = arsc.Library(
            orcabusId="SOME9ARSC9LIBRARY9ID12345",
            libraryId="L9900999"
        )
        test_arsc.libraries = list()
        test_arsc.libraries.append(lib_1)
        hash_1 = get_arsc_hash(test_arsc)
        assert hash_0 != hash_1, "Hash is the same!"

        # add another library and expect yet another hash
        lib_2 = arsc.Library(
            orcabusId="SOME9ARSC9LIBRARY9ID12345",
            libraryId="L9900999"
        )
        test_arsc.libraries.append(lib_2)
        hash_2 = get_arsc_hash(test_arsc)
        assert hash_0 != hash_2, "Hash is the same!"
        assert hash_1 != hash_2, "Hash is the same!"

        # add readsets to libs and expect hash to change
        readset_1 = arsc.Readset(
            orcabusId="SOME9ARSC9READSET9ID12345",
            rgid="AAGCAGTC+ACGCCAAC.1.990101_A00130_0999_BH7TVMDSX7",
        )
        readset_2 = arsc.Readset(
            orcabusId="SOME9ARSC9READSET9ID12346",
            rgid="AAGCAGTC+ACGCCAAC.2.990101_A00130_0999_BH7TVMDSX7",
        )
        readset_3 = arsc.Readset(
            orcabusId="SOME9ARSC9READSET9ID12347",
            rgid="AAGCAGTC+ACGCCAAC.3.990101_A00130_0999_BH7TVMDSX7",
        )
        readset_4 = arsc.Readset(
            orcabusId="SOME9ARSC9READSET9ID12348",
            rgid="AAGCAGTC+ACGCCAAC.4.990101_A00130_0999_BH7TVMDSX7",
        )
        lib_1.readsets = list()
        lib_1.readsets.append(readset_1)
        lib_1.readsets.append(readset_2)
        hash_1_1 = get_arsc_hash(test_arsc)
        assert hash_0 != hash_1_1, "Hash is the same!"  # different to original hash
        assert hash_1 != hash_1_1, "Hash is the same!"  # different to hash without readsets
        lib_1.readsets = list()
        lib_1.readsets.append(readset_2)
        lib_1.readsets.append(readset_1)
        hash_1_2 = get_arsc_hash(test_arsc)
        assert hash_0 != hash_1_2, "Hash is the same!"  # different to original hash
        assert hash_1 != hash_1_2, "Hash is the same!"  # different to hash without readsets
        assert hash_1_1 == hash_1_2, "Hash is not the same!"  # same as hash with readsets (in different order)

        lib_2.readsets = list()
        lib_2.readsets.append(readset_3)
        hash_2_1 = get_arsc_hash(test_arsc)
        assert hash_2 != hash_2_1, "Hash is the same!"  # different to hash without readsets
        lib_2.readsets.append(readset_4)
        hash_2_2 = get_arsc_hash(test_arsc)
        assert hash_2_1 != hash_2_2, "Hash is the same!"  # different to has with less readsets
