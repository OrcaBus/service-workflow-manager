import django

django.setup()

# --- keep ^^^ at top of the module
import logging
from workflow_manager_proc.domain.event import aru
from workflow_manager_proc.services.analysis_run import create_analysis_run, finalise_analysis_run

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SUPPORTED_ARU_STATUS = [
    "DRAFT",
    "READY",
]


def handler(event, context):
    """
    Parameters:
        event: JSON event conform to <glue>.AnalysisRunUpdate
        context: ignored for now (only used to conform to Lambda handler conventions)
    Procedure:
        Lambda wrapper around analysis_run depends on status DRAFT or READY
    """
    logger.info(f"Processing {event}, {context}")

    # remove the AWSEvent wrapper from our aru event
    input_event: aru.AWSEvent = aru.AWSEvent.model_validate_json(event)
    # get the actual AnalysisRunUpdate event object
    analysis_run_update: aru.AnalysisRunUpdate = input_event.detail

    # check supported ARU status
    if analysis_run_update.status.upper() not in SUPPORTED_ARU_STATUS:
        raise ValueError(f"Unsupported AnalysisRunUpdate status: {analysis_run_update.status}")

    match analysis_run_update.status.upper():
        case "DRAFT":
            # create the DB record from the event
            create_analysis_run(analysis_run_update)
        case "READY":
            # finalise the DB record based on the event
            finalise_analysis_run(analysis_run_update)

    logger.info(f"{__name__} done.")
