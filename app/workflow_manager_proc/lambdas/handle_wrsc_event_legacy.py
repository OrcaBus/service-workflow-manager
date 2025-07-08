import django

django.setup()

# --- keep ^^^ at top of the module
import logging
import workflow_manager.aws_event_bridge.executionservice.workflowrunstatechange as srv
from workflow_manager_proc.services.workflow_run import create_workflow_run

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Parameters:
        event: JSON event conform to <executionservice>.WorkflowRunStateChange
        context: ignored for now (only used to conform to Lambda handler conventions)
    Procedure:
        - Unpack AWS event
        - create new State for WorkflowRun if required
        - relay the state change as WorkflowManager WRSC event if applicable
    """
    logger.info(f"Processing {event}, {context}")

    # remove the AWSEvent wrapper from our WRSC event
    input_event: srv.AWSEvent = srv.Marshaller.unmarshall(event, srv.AWSEvent)
    input_wrsc: srv.WorkflowRunStateChange = input_event.detail

    _create_workflow_run_with_legacy_adapter(input_wrsc)

    logger.info(f"{__name__} done.")


def _create_workflow_run_with_legacy_adapter(legacy_wrsc_event: srv.WorkflowRunStateChange):

    # defensive about the incoming as an WRSC legacy event
    if legacy_wrsc_event.workflowName is None or legacy_wrsc_event.workflowVersion is None:
        raise ValueError("WRSC legacy schema error. The workflowName and workflowVersion must be defined.")

    # FIXME map legacy to new WRSC event with next PR
    adapted_wrsc_event = legacy_wrsc_event

    create_workflow_run(adapted_wrsc_event)
