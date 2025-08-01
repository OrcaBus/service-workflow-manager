import django

django.setup()

# --- keep ^^^ at top of the module
import logging
import workflow_manager.aws_event_bridge.executionservice.workflowrunstatechange as srv
from workflow_manager_proc.services.workflow_run_legacy import create_workflow_run

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

    # defensive about the incoming as an WRSC legacy event
    if input_wrsc.workflowName is None or input_wrsc.workflowVersion is None:
        raise ValueError("WRSC legacy schema error. The workflowName and workflowVersion must be defined.")

    create_workflow_run(input_wrsc)

    logger.info(f"{__name__} done.")
