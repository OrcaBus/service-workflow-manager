import django

django.setup()

# --- keep ^^^ at top of the module
import logging
from workflow_manager_proc.domain.event import wrsc_legacy
from workflow_manager_proc.services.workflow_run_legacy import create_workflow_run

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Parameters:
        event: JSON event conform to legacy WorkflowRunStateChange (flat fields)
        context: ignored for now (only used to conform to Lambda handler conventions)
    Procedure:
        - Unpack AWS event
        - create new State for WorkflowRun if required
        - relay the state change as WorkflowManager WRSC event if applicable
    """
    logger.info(f"Processing {event}, {context}")

    input_event = wrsc_legacy.AWSEvent.model_validate(event)
    input_wrsc: wrsc_legacy.WorkflowRunStateChange = input_event.detail

    if input_wrsc.workflowName is None or input_wrsc.workflowVersion is None:
        raise ValueError("WRSC legacy schema error. The workflowName and workflowVersion must be defined.")

    create_workflow_run(input_wrsc)

    logger.info(f"{__name__} done.")
