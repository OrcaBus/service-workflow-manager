import django

django.setup()

# --- keep ^^^ at top of the module
import logging
from workflow_manager_proc.services import emit_analysis_run_state_change, create_analysis_run
from workflow_manager_proc.domain.event import ari, arsc
from workflow_manager_proc.services.analysis_run import create_analysis_run

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Parameters:
        event: JSON event conform to <glue>.AnalysisRunInitiated
        context: ignored for now (only used to conform to Lambda handler conventions)
    Procedure:
        Lambda wrapper around analysis_run.finalise_analysis_run
    """
    logger.info(f"Processing {event}, {context}")

    # remove the AWSEvent wrapper from our ARI event
    input_event: ari.AWSEvent = ari.AWSEvent.model_validate_json(event)
    # get the actual AnalysisRunInitiated event object
    analysis_run_initial: ari.AnalysisRunInitiated = input_event.detail
    # Create the DB record from the event
    create_analysis_run(analysis_run_initial)

    logger.info(f"{__name__} done.")
