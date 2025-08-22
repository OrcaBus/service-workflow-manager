import hashlib
import logging
import os
import uuid

from django.db import transaction
from django.utils import timezone

from workflow_manager.models import (
    WorkflowRun,
    Workflow,
    Library,
    LibraryAssociation,
    State,
    Status, Payload, Readset,
)
from workflow_manager.models.run_context import RunContext, RunContextUseCase, RunContextStatus
from workflow_manager.models.utils import WorkflowRunUtil
from workflow_manager_proc.domain.event import wrsc, wru
from workflow_manager_proc.services.event_utils import emit_event, EventType

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ASSOCIATION_STATUS = "ACTIVE"
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME")
WRSC_SCHEMA_VERSION = "0.0.1"


def sanitize_orcabus_id(orcabus_id: str) -> str:
    # TODO: better sanitization and better location
    return orcabus_id[-26:]


@transaction.atomic
def create_workflow_run(event: wru.WorkflowRunUpdate):
    # check state list
    out_wrsc = _create_workflow_run(event)
    if out_wrsc:
        # new state resulted in state transition, we can relay the WRSC
        logger.info("Emitting WRSC.")
        emit_event(event_type=EventType.WRSC, event_bus=EVENT_BUS_NAME, event_json=out_wrsc.model_dump_json())
    else:
        # ignore - state has not been updated
        logger.info(f"WorkflowRun state not updated. No event to emit.")

    return out_wrsc


def _create_workflow_run(event: wru.WorkflowRunUpdate) -> wrsc.WorkflowRunStateChange | None:
    """
    Parameters:
        event: JSON event conform to WorkflowRunStateChange
    Procedure:
        - check whether a corresponding Workflow record exists (it should according to the pre-planning approach)
            - if not exist, create (support on-the-fly approach)
        - check whether a WorkflowRun record exists (it should if this is not the first/initial state)
            - if not exist, create
            - associate any libraries at this point (later updates/linking is not supported at this point)
        - check whether the state change event constitutes a new state
            - the DRAFT state allows payload updates, until it enters the READY state
            - the RUNNING state allows "infrequent" updates (i.e. that happen outside a certain time window)
            - other states will ignore updates of the same state
            - if we have new state, then persist it
            NOTE: all events that don't change any state value should be ignored
    """
    logger.info(f"Start processing {event}")

    # We expect: a corresponding Workflow has to exist for each workflow run
    # NOTE: for now we allow dynamic workflow creation
    # TODO: expect workflows to be pre-registered
    # TODO: could move that logic to caller and expect WF to exist here
    workflow = create_or_get_workflow(event)

    # Then create the actual workflow run entry if it does not exist
    wfr = create_or_get_workflow_run(event, workflow)

    success, new_state = update_workflow_run_to_new_state(event, wfr)

    if not success:
        logger.warning(f"Could not apply new state: {new_state}")
        return None

    out_wrsc = map_workflow_run_new_state_to_wrsc(wfr, new_state)

    logger.info(f"{__name__} done.")

    return out_wrsc


def create_or_get_workflow(event: wru.WorkflowRunUpdate):
    try:
        logger.info(f"Looking for Workflow ({event.workflow}).")
        workflow: Workflow = Workflow.objects.get(
            workflow_name=event.workflow.name,
            workflow_version=event.workflow.version,
            execution_engine=event.workflow.executionEngine
        )
    except Exception:
        logger.warning("No Workflow record found! Creating new entry.")
        workflow = Workflow(
            workflow_name=event.workflow.name,
            workflow_version=event.workflow.version,
            execution_engine=event.workflow.executionEngine,
            execution_engine_pipeline_id="Unknown",
        )
        logger.info("Persisting Workflow record.")
        workflow.save()

    return workflow


def create_or_get_workflow_run(event: wru.WorkflowRunUpdate, workflow: Workflow) -> WorkflowRun:
    try:
        wfr: WorkflowRun = WorkflowRun.objects.get(portal_run_id=event.portalRunId)
    except Exception:
        logger.info("No WorkflowRun record found! Creating new entry.")
        wfr = WorkflowRun(
            portal_run_id=event.portalRunId,
            workflow_run_name=event.workflowRunName,
            # execution_id=event.executionId,   # FIXME: No executionId in the event schema. How do we do it? For ICA, apparently analysis ID is in the Payload data tag for some workflow pipeline execution
            workflow=workflow,
        )
        logger.info(wfr)
        logger.info("Persisting WorkflowRun record.")
        wfr.save()

        # NOTE: the library linking is expected to be established at workflow run creation time.
        #       Later changes will currently be ignored.

        # if the workflow run is linked to library record(s), create the association(s)
        establish_workflow_run_libraries(event, wfr)

        # if the workflow run has contexts, create the association(s)
        establish_workflow_run_contexts(event, wfr)

    return wfr


def establish_workflow_run_libraries(event: wru.WorkflowRunUpdate, wfr: WorkflowRun) -> None:
    if not event.libraries:
        return

    for input_rec in event.libraries:
        # make sure OrcaBus ID format is sanitized (without prefix) for lookups
        orca_id = sanitize_orcabus_id(input_rec.orcabusId)
        # get the DB record of the library
        try:
            db_lib: Library = Library.objects.get(orcabus_id=orca_id)
        except Library.DoesNotExist:
            # The library record should exist - synced with metadata service on LibraryStateChange events
            # However, until that sync is in place we may need to create a record on demand
            # FIXME: remove this once library records are automatically synced
            db_lib = Library.objects.create(orcabus_id=orca_id, library_id=input_rec.libraryId)

        # create the library association
        LibraryAssociation.objects.create(
            workflow_run=wfr,
            library=db_lib,
            association_date=timezone.now(),
            status=ASSOCIATION_STATUS,
        )

        # if the library is linked to readset record(s), create the association(s)
        if input_rec.readsets:
            for rs in input_rec.readsets:
                rs_db, _ = Readset.objects.get_or_create(
                    orcabus_id=sanitize_orcabus_id(rs.orcabusId),
                    rgid=rs.rgid,
                    library_id=db_lib.library_id,
                    library_orcabus_id=db_lib.orcabus_id
                )
                wfr.readsets.add(rs_db)


def establish_workflow_run_contexts(event: wru.WorkflowRunUpdate, wfr: WorkflowRun) -> None:
    # process computeEnv
    if event.computeEnv:
        compute_run_ctx, _ = RunContext.objects.get_or_create(
            name=event.computeEnv,
            usecase=RunContextUseCase.COMPUTE.value,
        )
        wfr.contexts.add(compute_run_ctx)

    # process storageEnv
    if event.storageEnv:
        storage_run_ctx, _ = RunContext.objects.get_or_create(
            name=event.storageEnv,
            usecase=RunContextUseCase.STORAGE.value,
        )
        wfr.contexts.add(storage_run_ctx)


def update_workflow_run_to_new_state(event: wru.WorkflowRunUpdate, wfr: WorkflowRun) -> tuple[bool, State]:
    # Create a new State sub (not persisted)
    new_state = State(
        status=event.status,
        timestamp=event.timestamp if event.timestamp else timezone.now(),
    )

    # Handle the payload
    if event.payload:
        new_state.payload = Payload(
            payload_ref_id=str(uuid.uuid4()),
            version=event.payload.version,
            data=event.payload.data,
        )

    # Attempt to transition to new state (will persist new state if successful)
    success = WorkflowRunUtil(wfr).transition_to(new_state)

    return success, new_state


def map_workflow_run_new_state_to_wrsc(wfr: WorkflowRun, new_state: State) -> wrsc.WorkflowRunStateChange:
    out_wrsc = wrsc.WorkflowRunStateChange(
        id="",
        version=WRSC_SCHEMA_VERSION,
        timestamp=new_state.timestamp,
        orcabusId=wfr.orcabus_id,
        portalRunId=wfr.portal_run_id,
        workflowRunName=wfr.workflow_run_name,
        workflow=wrsc.Workflow(
            orcabusId=wfr.workflow.orcabus_id,
            name=wfr.workflow.workflow_name,
            version=wfr.workflow.workflow_version,
            executionEngine=wfr.workflow.execution_engine,
        ),
        status=Status.get_convention(new_state.status),  # ensure we follow conventions
    )

    # Set libraries
    if wfr.libraries:
        lib_list = []
        for in_lib in wfr.libraries.all():
            out_lib = wrsc.Library(
                orcabusId=in_lib.orcabus_id,
                libraryId=in_lib.library_id,
            )

            # Set readsets
            if wfr.readsets:
                rs_qs = wfr.readsets.filter(
                    library_id=in_lib.library_id,
                    library_orcabus_id=in_lib.orcabus_id,
                )
                if rs_qs.exists():
                    rs_list = []
                    for rs in rs_qs.all():
                        rs_list.append(wrsc.Readset(
                            orcabusId=rs.orcabus_id,
                            rgid=rs.rgid,
                        ))
                    if rs_list:
                        out_lib.readsets = rs_list
            lib_list.append(out_lib)
        if lib_list:
            out_wrsc.libraries = lib_list

    # Set AnalysisRun
    if wfr.analysis_run:
        out_wrsc.analysisRun = wrsc.AnalysisRun(
            orcabusId=wfr.analysis_run.orcabus_id,
            name=wfr.analysis_run.analysis_run_name,
        )

    # Set Payload
    # NOTE: the srv payload is not quite the same as the wfm payload (it's missing a payload ref id that's assigned by the wfm)
    # So, if the new state has a payload, we need to map the service payload to the wfm payload
    if new_state.payload:
        out_wrsc.payload = wrsc.Payload(
            orcabusId=new_state.payload.orcabus_id,
            refId=new_state.payload.payload_ref_id,
            version=new_state.payload.version,
            data=new_state.payload.data
        )

    # Set RunContext
    if wfr.contexts:
        # search active compute context, get the most recent one if exists
        compute_qs = wfr.contexts.filter(
            usecase=RunContextUseCase.COMPUTE.value,
            status=RunContextStatus.ACTIVE.value
        ).order_by("-orcabus_id")
        if compute_qs.exists():
            compute_ctx: RunContext = compute_qs.first()
            out_wrsc.computeEnv = compute_ctx.name

        # search active storage context, get the most recent one if exists
        storage_qs = wfr.contexts.filter(
            usecase=RunContextUseCase.STORAGE.value,
            status=RunContextStatus.ACTIVE.value
        ).order_by("-orcabus_id")
        if storage_qs.exists():
            storage_ctx: RunContext = storage_qs.first()
            out_wrsc.storageEnv = storage_ctx.name

    # Set ID by applying hash function
    out_wrsc.id = get_wrsc_hash(out_wrsc)

    return out_wrsc


def get_wrsc_hash(out_wrsc: wrsc.WorkflowRunStateChange) -> str:
    # if there is already a hash then we simply return that
    # TODO: allow force creation
    # TODO: include OrcaBus IDs or rely on entity values only?
    if out_wrsc.id:
        return out_wrsc.id

    # extract valuable keys from out_wrsc
    keywords = list()

    # out_wrsc values
    keywords.append(out_wrsc.version)
    # keywords.append(out_wrsc.timestamp.isoformat())  # ignoring time changes for now
    keywords.append(out_wrsc.orcabusId)
    keywords.append(out_wrsc.portalRunId)
    keywords.append(out_wrsc.workflowRunName)
    keywords.append(out_wrsc.status)
    keywords.append(out_wrsc.workflow.orcabusId)

    if out_wrsc.payload:
        keywords.append(out_wrsc.payload.orcabusId)

    if out_wrsc.analysisRun:
        keywords.append(out_wrsc.analysisRun.orcabusId)

    # add libraries
    if out_wrsc.libraries:
        for lib in out_wrsc.libraries:
            keywords.append(lib.orcabusId)

    # filter out any None values
    keywords = list(filter(None, keywords))
    # sort the list of keywords to avoid issues with record order
    keywords.sort()

    # create hash value
    md5_object = hashlib.md5()
    for key in keywords:
        md5_object.update(key.encode("utf-8"))

    return md5_object.hexdigest()
