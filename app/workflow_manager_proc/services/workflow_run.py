import datetime
import hashlib
import logging
import os

from django.db import transaction

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
from . import create_payload_stub_from_wrsc

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ASSOCIATION_STATUS = "ACTIVE"
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME")
WRSC_SCHEMA_VERSION = "0.0.1"


def sanitize_orcabus_id(orcabus_id: str) -> str:
    # TODO: better sanitization and better location
    return orcabus_id[-26:]


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
            workflow_name=srv_wrsc.workflowName, workflow_version=srv_wrsc.workflowVersion
        )
    except Exception:
        logger.warning("No Workflow record found! Creating new entry.")
        workflow = Workflow(
            workflow_name=srv_wrsc.workflowName,
            workflow_version=srv_wrsc.workflowVersion,
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
                    association_date=datetime.datetime.now(),
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
        new_state.payload = create_payload_stub_from_wrsc(srv_wrsc)

    # attempt to transition to new state (will persist new state if successful)
    success = wfr_util.transition_to(new_state)
    if not success:
        logger.warning(f"Could not apply new state: {new_state}")
        return None

    wfm_wrsc = _map_srv_wrsc_to_wfm_wrsc(wfr, srv_wrsc, new_state)

    logger.info(f"{__name__} done.")
    return wfm_wrsc


def _map_srv_wrsc_to_wfm_wrsc(wfr: WorkflowRun, input_wrsc: srv.WorkflowRunStateChange,
                             new_state: State) -> wrsc.WorkflowRunStateChange:
    lib_list = None
    if input_wrsc.linkedLibraries:
        lib_list = []
        for in_lib in input_wrsc.linkedLibraries:
            out_lib = wrsc.Library(
                orcabusId=in_lib.orcabusId,
                libraryId=in_lib.libraryId,
            )
            lib_list.append(out_lib)

    wrsc_analysis_run = None
    if wfr.analysis_run:
        wrsc_analysis_run = wrsc.AnalysisRun(
            orcabusId=wfr.analysis_run.orcabus_id,
            name=wfr.analysis_run.analysis_run_name,
        )

    out_wrsc = wrsc.WorkflowRunStateChange(
        id="",
        version=WRSC_SCHEMA_VERSION,
        timestamp=input_wrsc.timestamp,
        orcabusId=wfr.orcabus_id,
        portalRunId=input_wrsc.portalRunId,
        workflowRunName=input_wrsc.workflowRunName,
        workflow=wrsc.Workflow(
            orcabusId=wfr.workflow.orcabus_id,
            name=wfr.workflow.workflow_name,
            version=wfr.workflow.workflow_version,
            executionEngine=wfr.workflow.execution_engine,
        ),
        analysisRun=wrsc_analysis_run,
        libraries=lib_list,
        status=Status.get_convention(input_wrsc.status),  # ensure we follow conventions
    )
    # NOTE: the srv payload is not quite the same as the wfm payload (it's missing a payload ref id that's assigned by the wfm)
    # So, if the new state has a payload, we need to map the service payload to the wfm payload
    if new_state.payload:
        out_wrsc.payload = _map_srv_payload_to_wfm_payload(input_wrsc.payload, new_state.payload)

    out_wrsc.id = get_wrsc_hash(out_wrsc)
    return out_wrsc


def _map_srv_payload_to_wfm_payload(input_payload: srv.Payload, payload_db: Payload) -> wrsc.Payload:
    out_payload = wrsc.Payload(
        orcabusId=payload_db.orcabus_id,
        refId=payload_db.payload_ref_id,
        version=input_payload.version,
        data=input_payload.data
    )
    return out_payload


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
