import datetime
import os
import time
from unittest import mock

from workflow_manager.models import Library, Status, AnalysisContext, AnalysisRunState
from workflow_manager.models.analysis import Analysis
from workflow_manager.models.analysis_context import ContextUseCase
from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager_proc.domain.event import arsc, ari, arf
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

    def setUp(self) -> None:
        self.env_mock = mock.patch.dict(os.environ, {"EVENT_BUS_NAME": "FooBus"})
        self.env_mock.start()
        super().setUp()

    def tearDown(self) -> None:
        self.env_mock.stop()
        # self.clean_base_entities()
        super().tearDown()

    def setup_base_entities(self) -> None:
        # prepare basic prerequisites that are expected to be preconfigured in a real DB
        # e.g. Analysis, Libraries, AnalysisContexts, ...
        Analysis(
            orcabus_id=ANALYSIS_1_OID,
            analysis_name=ANALYSIS_1_NAME,
            analysis_version="0.0.1",
            description="Lorem Ipsum is simply dumb",
            status="FAKE"
        ).save()
        Library(
            orcabus_id="lib.123456789ABCDEFGHJKMNPQRST",
            library_id="L000001"
        ).save()
        Library(
            orcabus_id="lib.223456789ABCDEFGHJKMNPQRST",
            library_id="L000002"
        ).save()
        AnalysisContext(
            name="research",
            usecase=ContextUseCase.COMPUTE.value,
            description="Test Compute Context - Research",
            status="ACTIVE"
        ).save()
        AnalysisContext(
            name="research",
            usecase=ContextUseCase.STORAGE.value,
            description="Test Storage Context - Research",
            status="ACTIVE"
        ).save()

    def setup_arf_case_1(self) -> None:
        self.setup_base_entities()

        analysis = Analysis.objects.get(orcabus_id=ANALYSIS_1_OID)
        lib1 = Library.objects.get(library_id="L000001")
        lib2 = Library.objects.get(library_id="L000002")
        compute_context = AnalysisContext.objects.get(name="research", usecase=ContextUseCase.COMPUTE.value)
        storage_context = AnalysisContext.objects.get(name="research", usecase=ContextUseCase.STORAGE.value)

        analysis_run = AnalysisRun(
            orcabus_id="anr.ANR123456789ABCDEFGHJKMNPQ",
            analysis_run_name="TestAnalysisRunName_1",
            analysis=analysis,
            compute_context=compute_context,
            storage_context=storage_context,
        )
        analysis_run.libraries.add(lib1)
        analysis_run.libraries.add(lib2)
        analysis_run.save()
        AnalysisRunState(
            analysis_run=analysis_run,
            status=Status.DRAFT.convention,
            timestamp=datetime.datetime.strptime("01/05/2025 6:00", "%m/%d/%Y %H:%M")
        ).save()

    def clean_base_entities(self) -> None:
        Analysis.objects.all().delete()
        AnalysisContext.objects.all().delete()
        AnalysisRun.objects.all().delete()
        AnalysisRunState.objects.all().delete()
        Library.objects.all().delete()

    def test_ari_case_1(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_ari_case_1
        """

        script_dir = os.path.dirname(__file__)
        rel_path = "fixtures/ARI_event_1.json"
        logger.info(f"Loading test event data from {rel_path}")
        abs_file_path = os.path.join(script_dir, rel_path)
        with open(abs_file_path) as f:
            file_content = f.read()

        # Test the event loading, any exceptions will be raised
        logger.info("Event validation and mapping against event model...")
        ari_event = ari.AnalysisRunInitiated.model_validate_json(file_content)
        self.assertIsNotNone(ari_event)

        # Set up the required base entities
        self.setup_base_entities()

        logger.info("Testing DB record creation from event...")
        db_analysis_run = _create_analysis_run(ari_event)
        self.assertIsNotNone(db_analysis_run)
        self.assertEqual(db_analysis_run.analysis.analysis_name, ANALYSIS_1_NAME)
        self.assertEqual(db_analysis_run.analysis_run_name, "TestAnalysisRunName_1")
        self.assertEqual(db_analysis_run.get_latest_state().status, Status.DRAFT.convention)

        logger.info("ARSC event creation from DB record...")
        arsc_event = _map_analysis_run_to_arsc(db_analysis_run)
        self.assertIsNotNone(arsc_event)
        test_id = get_arsc_hash(arsc_event)
        self.assertEqual(test_id, arsc_event.id)
        # TODO: how to test that the id is stable / does not change?
        # NOTE: we can't really test it as the new generation of the AnalysisRun record
        #       will assign a new OrcaBus ID each time.

        logger.info("ARSC event created: ")
        logger.info(arsc.AnalysisRunStateChange.model_dump_json(arsc_event))

    def test_arf_case_1(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_arf_case_1
        """

        script_dir = os.path.dirname(__file__)
        rel_path = "fixtures/ARF_event_1.json"
        logger.info(f"Loading test event data from {rel_path}")
        abs_file_path = os.path.join(script_dir, rel_path)
        with open(abs_file_path) as f:
            file_content = f.read()

        # Test the event loading, any exceptions will be raised
        logger.info("Event validation and mapping against event model...")
        arf_event = arf.AnalysisRunFinalised.model_validate_json(file_content)
        self.assertIsNotNone(arf_event)

        # Before we can process the event we need to fulfil its requirements
        # This event expects to finalise an existing record
        self.setup_arf_case_1()

        logger.info("Testing DB record update from event...")
        db_analysis_run = _finalise_analysis_run(arf_event)
        self.assertIsNotNone(db_analysis_run)
        self.assertEqual(db_analysis_run.analysis.analysis_name, ANALYSIS_1_NAME)
        self.assertEqual(db_analysis_run.analysis_run_name, "TestAnalysisRunName_1")
        # the state has to be READY now, as we processed a finalisation event
        self.assertEqual(db_analysis_run.get_latest_state().status, Status.READY.convention)

        logger.info("ARSC event creation from DB record...")
        arsc_event = _map_analysis_run_to_arsc(db_analysis_run)
        self.assertIsNotNone(arsc_event)
        test_id = get_arsc_hash(arsc_event)
        self.assertEqual(test_id, arsc_event.id)
        # TODO: how to test that the id is stable / does not change?
        # NOTE: we can't really test it as the new generation of the AnalysisRun record
        #       will assign a new OrcaBus ID each time.

        logger.info("ARSC event created: ")
        logger.info(arsc.AnalysisRunStateChange.model_dump_json(arsc_event))

    def test_ari_arf_case_1(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_ari_arf_case_1

        Test the AnalysisRun creation via ARI event and finalisation via following ARF event.
        This should test the common case of AnalysisRun creation by external execution services.
        """
        script_dir = os.path.dirname(__file__)
        rel_path_ari = "fixtures/ARI_event_1.json"
        rel_path_arf = "fixtures/ARF_event_1.json"
        logger.info(f"Loading ARI event data from {rel_path_ari}")
        logger.info(f"Loading ARF event data from {rel_path_arf}")
        abs_file_path_ari = os.path.join(script_dir, rel_path_ari)
        abs_file_path_arf = os.path.join(script_dir, rel_path_arf)
        with open(abs_file_path_ari) as f:
            file_content_ari = f.read()
        with open(abs_file_path_arf) as f:
            file_content_arf = f.read()

        logger.info("Event validation and mapping against event model...")
        ari_event = ari.AnalysisRunInitiated.model_validate_json(file_content_ari)
        arf_event = arf.AnalysisRunFinalised.model_validate_json(file_content_arf)
        self.assertIsNotNone(ari_event)
        self.assertIsNotNone(arf_event)

        # Set up the required base entities
        self.setup_base_entities()

        # Initiate the AnalysisRun with the ARI event
        db_analysis_run_ari = _create_analysis_run(ari_event)
        # make sure the AnalysisRun ID of the ARF event matches the ID created for the ARI event
        self.assertEqual(db_analysis_run_ari.get_latest_state().status, Status.DRAFT.convention)
        arf_event.orcabusId = db_analysis_run_ari.orcabus_id
        # Finalise the AnalysisRun with the ARF event
        db_analysis_run_arf = _finalise_analysis_run(arf_event)
        self.assertEqual(db_analysis_run_arf.get_latest_state().status, Status.READY.convention)

        # run some spot checks
        self.assertEqual(db_analysis_run_ari.analysis, db_analysis_run_arf.analysis)
        self.assertEqual(db_analysis_run_ari.analysis_run_name, db_analysis_run_arf.analysis_run_name)
        self.assertEqual(db_analysis_run_ari.orcabus_id, db_analysis_run_arf.orcabus_id)

    def test_ari_arf_case_2(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_ari_arf_case_2

        Test the AnalysisRun creation via ARI event and finalisation via following ARF event.
        This should test the common case of AnalysisRun creation by external execution services.
        """
        # Assume an AnalysisRun has already been created and finalised
        self.test_ari_arf_case_1()

        # then receive a new ARI event for the same AnalysisRun
        script_dir = os.path.dirname(__file__)
        rel_path_ari = "fixtures/ARI_event_1.json"
        logger.info(f"Loading ARI event data from {rel_path_ari}")
        abs_file_path_ari = os.path.join(script_dir, rel_path_ari)
        with open(abs_file_path_ari) as f:
            file_content_ari = f.read()

        logger.info("Event validation and mapping against event model...")
        ari_event = ari.AnalysisRunInitiated.model_validate_json(file_content_ari)
        self.assertIsNotNone(ari_event)

        # Initiate the AnalysisRun with the ARI event

        with self.assertRaises(Exception) as err:
            _create_analysis_run(ari_event)
        self.assertEqual(str(err.exception), 'AnalysisRun record already exists!')

    def test_ari_arf_case_3(self):
        """
        python manage.py test workflow_manager_proc.tests.test_analysis_run.AnalysisRunUnitTests.test_ari_arf_case_3

        Test the AnalysisRun creation via ARI event and finalisation via following ARF event.
        This should test the common case of AnalysisRun creation by external execution services.
        """
        # Assume an AnalysisRun has already been created and finalised
        self.test_ari_arf_case_1()

        # then receive a new ARI event for the same AnalysisRun
        script_dir = os.path.dirname(__file__)
        rel_path_arf = "fixtures/ARF_event_1.json"
        logger.info(f"Loading ARF event data from {rel_path_arf}")
        abs_file_path_arf = os.path.join(script_dir, rel_path_arf)
        with open(abs_file_path_arf) as f:
            file_content_arf = f.read()

        logger.info("Event validation and mapping against event model...")
        arf_event = ari.AnalysisRunInitiated.model_validate_json(file_content_arf)
        self.assertIsNotNone(arf_event)

        # Initiate the AnalysisRun with the ARI event

        with self.assertRaises(Exception) as err:
            _create_analysis_run(arf_event)
        self.assertEqual(str(err.exception), 'AnalysisRun record already exists!')

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
            status="TESTING"
        )
        hash_0 = get_arsc_hash(test_arsc)
        time.sleep(2)
        hash_x = get_arsc_hash(test_arsc)
        assert hash_0 == hash_x, "Hash isn't that same!"

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
