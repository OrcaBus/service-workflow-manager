import django

django.setup()

# --- keep ^^^ at top of the module
import logging
from workflow_manager_proc.domain.event import arf
from workflow_manager_proc.services.analysis_run import finalise_analysis_run

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Parameters:
        event: JSON event conform to <glue>.AnalysisRunFinalised
        context: ignored for now (only used to conform to Lambda handler conventions)
    Procedure:
        Lambda wrapper around analysis_run.finalise_analysis_run
    """
    logger.info(f"Processing {event}, {context}")

    # remove the AWSEvent wrapper from our ARI event
    # NOTE: mapping the json to the object model should ensure schema compliancy
    #       Any errors or missing data should result in an exception being raised
    # TODO: test this
    input_event: arf.AWSEvent = arf.AWSEvent.model_validate_json(event)
    # get the actual AnalysisRunFinalised event object
    analysis_run_final: arf.AnalysisRunFinalised = input_event.detail
    # Finalise the DB record based on the event
    finalise_analysis_run(analysis_run_final)

    logger.info(f"{__name__} done.")
