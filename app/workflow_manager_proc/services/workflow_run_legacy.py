"""
Deprecation note:
    We shall simply remove this module one day.
    This is retained here for backwards compatibility by Stacky execution engine.
    Most of this module impl is superseded by `workflow_run.py` with the newer WRSC event schema.
"""
import logging
import uuid

from django.db import transaction
from django.utils import timezone

import workflow_manager.aws_event_bridge.executionservice.workflowrunstatechange as srv
from workflow_manager.models import (
    WorkflowRun,
    Workflow,
    Library,
    LibraryAssociation,
    State,
    Status, Payload,
)
from workflow_manager.models.utils import WorkflowRunUtil
from workflow_manager_proc.domain.event import wrsc
from workflow_manager_proc.services.event_utils import emit_event, EventType
from workflow_manager_proc.services.workflow_run import EVENT_BUS_NAME, ASSOCIATION_STATUS, WRSC_SCHEMA_VERSION, \
    sanitize_orcabus_id, get_wrsc_hash

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@transaction.atomic
def create_workflow_run(event: srv.WorkflowRunStateChange):
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


def _create_workflow_run(event: srv.WorkflowRunStateChange):
    """
    Parameters:
        event: JSON event conform to <executionservice>.WorkflowRunStateChange
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
    srv_wrsc: srv.WorkflowRunStateChange = event

    # We expect: a corresponding Workflow has to exist for each workflow run
    # NOTE: for now we allow dynamic workflow creation
    # TODO: expect workflows to be pre-registered
    # TODO: could move that logic to caller and expect WF to exist here
    try:
        logger.info(f"Looking for Workflow ({srv_wrsc.workflowName}:{srv_wrsc.workflowVersion}).")
        workflow: Workflow = Workflow.objects.get(
            name=srv_wrsc.workflowName, version=srv_wrsc.workflowVersion
        )
    except Exception:
        logger.warning("No Workflow record found! Creating new entry.")
        workflow = Workflow(
            name=srv_wrsc.workflowName,
            version=srv_wrsc.workflowVersion,
            execution_engine="Unknown",
            execution_engine_pipeline_id="Unknown",
        )
        logger.info("Persisting Workflow record.")
        workflow.save()

    # then create the actual workflow run entry if it does not exist
    try:
        wfr: WorkflowRun = WorkflowRun.objects.get(portal_run_id=srv_wrsc.portalRunId)
    except Exception:
        logger.info("No WorkflowRun record found! Creating new entry.")
        # NOTE: the library linking is expected to be established at workflow run creation time.
        #       Later changes will currently be ignored.
        wfr = WorkflowRun(
            workflow=workflow,
            portal_run_id=srv_wrsc.portalRunId,
            execution_id=srv_wrsc.executionId,  # the execution service WRSC does carry the execution ID
            workflow_run_name=srv_wrsc.workflowRunName,
            comment=None
        )
        logger.info(wfr)
        logger.info("Persisting WorkflowRun record.")
        wfr.save()

        # if the workflow run is linked to library record(s), create the association(s)
        input_libraries: list[srv.LibraryRecord] = srv_wrsc.linkedLibraries
        if input_libraries:
            for input_rec in input_libraries:
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

    wfr_util = WorkflowRunUtil(wfr)

    # Create a new State sub (not persisted)
    new_state = State(
        status=srv_wrsc.status,
        timestamp=srv_wrsc.timestamp,
    )
    if srv_wrsc.payload:
        # handle the payload
        new_state.payload = Payload(
            payload_ref_id=str(uuid.uuid4()),
            version=srv_wrsc.payload.version,
            data=srv_wrsc.payload.data,
        )

    # attempt to transition to new state (will persist new state if successful)
    success = wfr_util.transition_to(new_state)
    if not success:
        logger.warning(f"Could not apply new state: {new_state}")
        return None

    wfm_wrsc = _map_srv_wrsc_to_wfm_wrsc(wfr, new_state, srv_wrsc)

    logger.info(f"{__name__} done.")
    return wfm_wrsc


def _map_srv_wrsc_to_wfm_wrsc(wfr: WorkflowRun, new_state: State, srv_wrsc) -> wrsc.WorkflowRunStateChange:
    out_wrsc = wrsc.WorkflowRunStateChange(
        id="",
        version=WRSC_SCHEMA_VERSION,
        timestamp=new_state.timestamp,
        orcabusId=wfr.orcabus_id,
        portalRunId=wfr.portal_run_id,
        workflowRunName=wfr.workflow_run_name,
        workflow=wrsc.Workflow(
            orcabusId=wfr.workflow.orcabus_id,
            name=wfr.workflow.name,
            version=wfr.workflow.version,
            executionEngine=wfr.workflow.execution_engine,
        ),
        status=Status.get_convention(new_state.status),  # ensure we follow conventions
    )

    # Set libraries as-is input event
    if srv_wrsc.linkedLibraries:
        lib_list = []
        for in_lib in srv_wrsc.linkedLibraries:
            out_lib = wrsc.Library(
                orcabusId=in_lib.orcabusId,
                libraryId=in_lib.libraryId,
            )
            lib_list.append(out_lib)
        if lib_list:
            out_wrsc.libraries = lib_list

    # Set AnalysisRun
    if wfr.analysis_run:
        wrsc_analysis_run = wrsc.AnalysisRun(
            orcabusId=wfr.analysis_run.orcabus_id,
            name=wfr.analysis_run.analysis_run_name,
        )
        out_wrsc.analysis_run = wrsc_analysis_run

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

    # Set ID by applying hash function
    out_wrsc.id = get_wrsc_hash(out_wrsc)

    return out_wrsc
