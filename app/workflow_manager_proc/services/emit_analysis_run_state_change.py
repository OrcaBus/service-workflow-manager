import os
import boto3
from workflow_manager_proc.domain.event.arsc import AnalysisRunStateChange
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

client = boto3.client('events', region_name='ap-southeast-2')
SOURCE = "orcabus.workflowmanager"
EVENT_BUS_NAME = os.environ["EVENT_BUS_NAME"]
DETAIL_TYPE = "AnalysisRunStateChange"


def handler(event, context):
    """
    event has to be JSON conform to workflowmanager.AnalysisRunStateChange
    """
    logger.info(f"Processing {event}, {context}")

    # Verify event against expected schema/model
    # TODO: strictly speaking this is not a schema validation!
    # NOTE: will raise a pydantic.ValidationError if the event does not conform to the model
    arsc = AnalysisRunStateChange.model_validate_json(event)

    response = client.put_events(
        Entries=[
            {
                'Source': SOURCE,
                'DetailType': DETAIL_TYPE,
                'Detail': arsc.model_dump_json(),
                'EventBusName': EVENT_BUS_NAME,
            },
        ],
    )

    logger.info(f"Sent a ARSC event to event bus {EVENT_BUS_NAME}:")
    logger.info(f"{__name__} done.")
    return response
