import django

from workflow_manager.models import Status

django.setup()

# --- keep ^^^ at top of the module
import logging
from workflow_manager_proc.domain.event import aru
from workflow_manager_proc.services.analysis_run import create_analysis_run, finalise_analysis_run


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SUPPORTED_ARU_STATUS = [
    Status.DRAFT.convention,
    Status.READY.convention,
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
    input_aru_with_envelope: aru.AWSEvent = aru.AWSEvent.model_validate(event)
    # get the actual AnalysisRunUpdate event object
    input_aru: aru.AnalysisRunUpdate = input_aru_with_envelope.detail

    # ensure ARU status are as expected
    assert input_aru.status.upper() in SUPPORTED_ARU_STATUS, "Unexpected AnalysisRun status!"

    match input_aru.status.upper():
        # TODO: This currently assumes that there will be exactly one DRAFT event followed by exactly one READY event.
        #       This was the initial assumption coming from two different event types (ARI/ARF).
        #       With a unified event type (ARU) we can be more flexible, e.g. allow multiple DRAFT events.
        #       However, there is no current use case for it, so we don't support it (yet).
        case Status.DRAFT.convention:
            # create the DB record from the event
            create_analysis_run(input_aru)
        case Status.READY.convention:
            # finalise the DB record based on the event
            finalise_analysis_run(input_aru)

    logger.info(f"{__name__} done.")
