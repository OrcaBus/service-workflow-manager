import hashlib
import logging
import os

from django.db import transaction
from django.db.models.query import QuerySet
from django.utils import timezone

from workflow_manager.models.analysis import Analysis
from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager.models.analysis_run_state import AnalysisRunState
from workflow_manager.models.library import Library
from workflow_manager.models.readset import Readset
from workflow_manager.models.run_context import RunContext, RunContextUseCase
from workflow_manager.models.utils import Status
from workflow_manager_proc.domain.event import arsc, aru
from workflow_manager_proc.services import analysis_run_utils
from workflow_manager_proc.services.event_utils import emit_event, EventType

logger = logging.getLogger()
logger.setLevel(logging.INFO)

EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME")
ARSC_SCHEMA_VERSION = "0.0.1"  # TODO: set somewhere more global (and check against schema?)


@transaction.atomic
def create_analysis_run(event: aru.AnalysisRunUpdate) -> None:
    db_record = _create_analysis_run(event)
    mapped_arsc = _map_analysis_run_to_arsc(db_record)
    logger.info("Emitting ARSC.")
    emit_event(event_type=EventType.ARSC, event_bus=EVENT_BUS_NAME, event_json=mapped_arsc.model_dump_json())
    logger.info("ARSC emitted.")


def _create_analysis_run(event: aru.AnalysisRunUpdate) -> AnalysisRun:
    """
    Parameters:
        event: the AnalysisRunUpdate event object to create the AnalysisRun from
    Procedure:
        - check whether a corresponding Analysis record exists (it should according to the pre-planning approach)
            - if not exist, raise an error
        - check whether a AnalysisRun record exists (it should not as this is run initiation)
            - if exists, raise an error
        - create a new AnalysisRun record
            - associate any libraries at this point (later updates/linking is not supported at this point)
        - create a new AnalysisRunStateChange record to be returned as result of the AnalysisRun creation
    """
    logger.info(f"Start processing ARU: {event}")
    # assert DRAFT status
    assert event.status.upper() == Status.DRAFT.convention, "AnalysisRunUpdate: Unexpected state!"

    analysis_event: aru.Analysis = event.analysis

    # We expect the corresponding Analysis to exist
    try:
        logger.info(
            f"Looking for Analysis ({analysis_event.name}:{analysis_event.version}) with id {analysis_event.orcabusId}.")
        analysis_db: Analysis = Analysis.objects.get(
            orcabus_id = analysis_event.orcabusId
        )
    except Exception as e:
        logger.error("No Analysis record found!")
        raise e

    # Create the AnalysisRun for this event
    # NOTE: since we process an Initiated event, we expect that the AnalysisRun does NOT exist yet
    analysis_run_db: QuerySet = AnalysisRun.objects.filter(analysis_run_name=event.analysisRunName)
    if analysis_run_db.exists():
        raise Exception("AnalysisRun record already exists!")
    else:
        logger.info("No AnalysisRun record found! Creating new entry.")
        analysis_run = AnalysisRun(
            analysis_run_name=event.analysisRunName,
            analysis=analysis_db,
        )
        analysis_run.save()
        # associate the DRAFT status
        AnalysisRunState(
            analysis_run=analysis_run,
            status=Status.DRAFT.convention,
            timestamp=timezone.now(),
        ).save()

        # attach the libraries associated with the AnalysisRunUpdate
        for aru_lib in event.libraries:
            # get the DB record of the library
            try:
                db_lib: Library = Library.objects.get(orcabus_id=aru_lib.orcabusId)
            except Library.DoesNotExist:
                # The library record should exist - synced with metadata service on LibraryStateChange events
                # However, until that sync is in place we may need to create a record on demand
                # FIXME: remove this once library records are automatically synced
                db_lib = Library.objects.create(orcabus_id=aru_lib.orcabusId, library_id=aru_lib.libraryId)

            # At this point we have a Library record, so we add that
            analysis_run.libraries.add(db_lib)

            # if we also have readset associated with this library, then associate them
            if aru_lib.readsets:
                for rs in aru_lib.readsets:
                    db_rs, _ = Readset.objects.get_or_create(
                        orcabus_id=rs.orcabusId,
                        rgid=rs.rgid,
                        library_id=db_lib.library_id,
                        library_orcabus_id=db_lib.orcabus_id,
                    )
                    analysis_run.readsets.add(db_rs)

        if event.computeEnv:
            rc = RunContext.objects.get_by_keyword(
                usecase=RunContextUseCase.COMPUTE.value,
                name=event.computeEnv
            ).first()
            analysis_run.contexts.add(rc)

        if event.storageEnv:
            rc = RunContext.objects.get_by_keyword(
                usecase=RunContextUseCase.STORAGE.value,
                name=event.storageEnv
            ).first()
            analysis_run.contexts.add(rc)

    logger.info(analysis_run)
    analysis_run.save()
    logger.info("AnalysisRun creation complete.")
    return analysis_run


@transaction.atomic
def finalise_analysis_run(event: aru.AnalysisRunUpdate):
    db_record = _finalise_analysis_run(event)
    mapped_arsc = _map_analysis_run_to_arsc(db_record)
    logger.info("Emitting ARSC.")
    emit_event(event_type=EventType.ARSC, event_bus=EVENT_BUS_NAME, event_json=mapped_arsc.model_dump_json())
    # TODO: add WorkflowRun DRAFT generation for workflows in analysis
    _create_workflow_runs_for_analysis_run(mapped_arsc)
    logger.info("ARSC emitted.")


def _finalise_analysis_run(event: aru.AnalysisRunUpdate) -> AnalysisRun:
    """
    Parameters:
        event: AnalysisRunUpdate event object to update the AnalysisRun from
    Procedure:
        - Unpack AWS event
        - create new State for AnalysisRun if required
        - relay the state change as WorkflowManager ARSC event if applicable
    """
    logger.info("Start processing AnalysisRunUpdate event:")
    logger.info(event)

    # Since we are finalising, we expect a corresponding record to exist already
    # Note: this will raise an exception if the record does NOT exist (or there are multiple)
    analysis_run_db: AnalysisRun = AnalysisRun.objects.get(orcabus_id=event.orcabusId)
    assert analysis_run_db is not None, f"AnalysisRunUpdate: AnalysisRun record does not exist!"

    # ensure the current state is DRAFT before we transition to READY
    assert analysis_run_db.get_latest_state().status == Status.DRAFT.convention, "Cannot finalise record that is not in DRAFT state!"

    # AnalysisRunId: can't be updated, has to match
    assert event.orcabusId == analysis_run_db.orcabus_id, "AnalysisRun IDs don't match!"
    # AnalysisRunName: can't be updated, has to match
    assert event.analysisRunName == analysis_run_db.analysis_run_name, "AnalysisRun names do not match!"

    # Analysis: can't be updated, has to match if present
    analysis_aru: aru.Analysis = event.analysis
    if analysis_aru:
        if analysis_aru.orcabusId:
            assert analysis_aru.orcabusId == analysis_run_db.analysis.orcabus_id, "Analysis IDs don't match!"
        if analysis_aru.name:
            assert analysis_aru.name == analysis_run_db.analysis.analysis_name, "AnalysisNames don't match!"
        if analysis_aru.version:
            assert analysis_aru.version == analysis_run_db.analysis.analysis_version, "AnalysisVersions don't match!"

    # ComputeEnv / StorageEnv: mandatory, can be provided
    # if the same env is already set on the DB record, then nothing to do
    # but if it does not exist or they are not the same, we need to update
    # It does not matter if the entry exists or not the value from the event takes precedence
    if event.computeEnv:
        compute_context: RunContext = RunContext.objects.get(
            name=event.computeEnv,
            usecase=RunContextUseCase.COMPUTE.value
        )  # name + usecase => unique
        analysis_run_db.contexts.add(compute_context)

    if event.storageEnv:
        storage_context: RunContext = RunContext.objects.get(
            name=event.storageEnv,
            usecase=RunContextUseCase.STORAGE.value
        )  # name + usecase => unique
        analysis_run_db.contexts.add(storage_context)

    # Libraries: are mandatory, but cannot be changed
    # Readsets: are mandatory, but Readsets can be added (if not present yet)
    assert len(event.libraries) == len(analysis_run_db.libraries.all()), "Libraries don't match!"

    # NOTE: Readsets on the event are attributes of a library.
    #       However, on the DB side they are directly linked to the AnalysisRun and not to the Library.
    rss_db = set(analysis_run_db.readsets.all())  # keep track of all Readsets that are already attached
    # Now check each library of the event and check the associated readsets whether they match the DB records
    logger.info("Finalising associated libraries")
    for l in event.libraries:
        lid = l.libraryId
        lod = l.orcabusId
        # assert that the DB record has the according Library record linked
        # ensure orcabus_id and library_id of the library are mapped to the same record
        assert analysis_run_db.libraries.get(library_id=lid) == analysis_run_db.libraries.get(orcabus_id=lod)
        rss = l.readsets
        for rs in rss:
            logger.info("Finalising associated readsets")
            if len(rss_db) > 0:
                logger.info("Readsets exist.")
                # check event readset against the DB readsets
                rs_db: Readset = analysis_run_db.readsets.filter(orcabus_id=rs.orcabusId).first()
                if rs_db:
                    # if the readset exists already, make sure it's for the same library
                    assert rs_db.library_orcabus_id == lod, "AnalysisRun Readset Library ID does not match!"
                    assert rs_db.library_id == lid, "AnalysisRun Readset Library ID does not match!"
                    rss_db.remove(rs_db)  # remove the readset from the tracker
            else:
                # No readsets associated with the AnalysisRun DB record, create new Readset and link it to AnalysisRun
                rs_db = Readset.objects.create(
                    orcabus_id=rs.orcabusId,
                    rgid=rs.rgid,
                    library_id=lid,
                    library_orcabus_id=lod,
                )
                analysis_run_db.readsets.add(rs_db)
    # Now we deal with the Readsets that were already attached, but were no longer part of the finalised event
    # In the first instance we don't allow this and fail if there are inconsistencies
    # TODO: in the future we could drop any records that are not confirmed in the finalisation event
    assert len(rss_db) == 0, f"Unmatched readsets for AnalysisRun, {rss_db}!"

    # no issues, then associate new status and emit ARSC event
    logger.info("Finalising associated run state")
    AnalysisRunState(
        analysis_run=analysis_run_db,
        status=Status.READY.convention,
        timestamp=timezone.now(),
    ).save()
    analysis_run_db.save()
    return analysis_run_db


def _map_analysis_run_to_arsc(analysis_run: AnalysisRun) -> arsc.AnalysisRunStateChange:
    lib_list = list()
    for l in analysis_run.libraries.all():
        # create arsc library record
        library = arsc.Library(
            orcabusId=l.orcabus_id,
            libraryId=l.library_id,
            readsets=None
        )
        # find all readsets of the run with the same library ids
        rs_set = analysis_run.readsets.filter(library_id=l.library_id, library_orcabus_id=l.orcabus_id)
        if rs_set.count() > 0:
            library.readsets = list()
        # create arsc readset records and add to the arsc library record
        for rs in rs_set:
            library.readsets.append(arsc.Readset(
                orcabusId=rs.orcabus_id,
                rgid=rs.rgid
            ))
        lib_list.append(library)

    current_state: AnalysisRunState = analysis_run.get_latest_state()

    # fetch the compute env if there is one
    compute_envs = analysis_run.contexts.filter(usecase=RunContextUseCase.COMPUTE.value)
    assert compute_envs.count() <= 1, "Multiple Compute Envs are currently not supported!"
    compute_env = None
    if compute_envs.count() == 1:
        compute_env = compute_envs.first().name

    # fetch the storage env if there is one
    storage_envs = analysis_run.contexts.filter(usecase=RunContextUseCase.STORAGE.value)
    assert storage_envs.count() <= 1, "Multiple Storage Envs are currently not supported!"
    storage_env = None
    if storage_envs.count() == 1:
        storage_env = storage_envs.first().name

    arsc_object = arsc.AnalysisRunStateChange(
        id="",  # mandatory field, need to provide a default value
        version=ARSC_SCHEMA_VERSION,
        orcabusId=analysis_run.orcabus_id,
        timestamp=current_state.timestamp,  # use the timestamp of the state change, not the mapping/event
        status=current_state.status,
        analysisRunName=analysis_run.analysis_run_name,
        analysis=arsc.Analysis(
            orcabusId=analysis_run.analysis.orcabus_id,
            name=analysis_run.analysis.analysis_name,
            version=analysis_run.analysis.analysis_version
        ),
        libraries=lib_list,
        computeEnv=compute_env,
        storageEnv=storage_env,
    )
    # add the unique event ID (hash of the event data)
    arsc_hash = get_arsc_hash(arsc_object)
    arsc_object.id = arsc_hash
    return arsc_object


def get_arsc_hash(ar_state: arsc.AnalysisRunStateChange) -> str:
    # if there is already a hash then we simply return that
    # TODO: allow force creation
    # TODO: include OrcaBus IDs or rely on entity values only?
    if ar_state.id:
        logger.info("ARSC already has a hash id. Skipping calculation.")
        return ar_state.id

    # extract valuable keys from ARSC
    keywords = list()

    # ARSC values
    keywords.append(ar_state.version)
    keywords.append(ar_state.orcabusId)
    # keywords.append(arsc.timestamp.isoformat())  # ignoring time changes for now
    keywords.append(ar_state.status)
    keywords.append(ar_state.analysisRunName)
    keywords.append(ar_state.computeEnv)
    keywords.append(ar_state.storageEnv)
    keywords.append(ar_state.analysis.orcabusId)

    # add libraries and their readsets
    if ar_state.libraries:
        for lib in ar_state.libraries:
            keywords.append(lib.orcabusId)
            if lib.readsets:
                for readset in lib.readsets:
                    keywords.append(readset.orcabusId)

    # filter out any None values
    keywords = list(filter(None, keywords))
    # sort the list of keywords to avoid issues with record order
    keywords.sort()
    logger.info(f"ANR hash keys: {keywords}")

    # create hash value
    md5_object = hashlib.md5()
    for key in keywords:
        md5_object.update(key.encode("utf-8"))

    return md5_object.hexdigest()


def _create_workflow_runs_for_analysis_run(analysis_run: arsc.AnalysisRunStateChange) -> None:
    """
    Create WorkflowRun records for the AnalysisRun based on its state transition to READY.
    Args:
        analysis_run: the AnalysisRunStateChange announcing the READY state of the AnalysisRun to create WorkflowRuns for. Note: has to be READY state.
    Returns: None. Returns are handled internally via event emissions if/when required.
    """
    # assert we operate on the correct state
    assert analysis_run.status.upper() == Status.READY.convention, "Expected READY state!"

    # TODO: handle the case where we receive the same READY event multiple times
    #       (don't want to create WorkflowRun records twice).
    #       Currently covered by the _finalise_analysis_run method,
    #       but perhaps an explicit state transition validator would be better
    # then create the WorkflowRun records for this AnalysisRun
    analysis_run_utils.create_workflows_runs_from_analysis_run(analysis_run)
