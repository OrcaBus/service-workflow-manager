import django

django.setup()

# --- keep ^^^ at top of the module
import logging

from workflow_manager_proc.domain.event import wru
from workflow_manager_proc.services import workflow_run

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Parameters:
        event: JSON event conform to WorkflowRunUpdate
        context: ignored for now (only used to conform to Lambda handler conventions)
    Procedure:
        - Unpack AWS event
        - create new State for WorkflowRun if required
        - relay the state change as WorkflowManager WRSC event if applicable
    """
    logger.info(f"Processing {event}, {context}")

    input_wru_with_envelope = wru.AWSEvent.model_validate(event)
    input_wru: wru.WorkflowRunUpdate = input_wru_with_envelope.detail

    workflow_run.create_workflow_run(input_wru)

    logger.info(f"{__name__} done.")
