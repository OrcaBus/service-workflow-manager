import os
import boto3
import logging
from enum import Enum
from workflow_manager_proc.domain.event import arsc, wrsc

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

client = boto3.client('events', region_name='ap-southeast-2')
SOURCE = "orcabus.workflowmanager"
EVENT_BUS_NAME = os.environ["EVENT_BUS_NAME"]


class EventType(Enum):
    WRSC = "WorkflowRunStateChange"
    ARSC = "AnalysisRunStateChange"


def emit_event(event_type: EventType, event_json):
    """
    Parameters:
        event_type: the type of event to emit using EventType
        event_json: the JSON string of the event
    """

    # Check that the provided event json matches the schema requirements
    # TODO: check that this actually works
    if event_type == EventType.WRSC:
        wrsc.WorkflowRunStateChange.model_validate_json(event_json)
    elif event_type == EventType.ARSC:
        arsc.AnalysisRunStateChange.model_validate_json(event_json)
    else:
        raise Exception(f"Unsupported event type: {event_type}")

    response = client.put_events(
        Entries=[
            {
                'Source': SOURCE,
                'DetailType': event_type.value,
                'Detail': event_json,
                'EventBusName': EVENT_BUS_NAME,
            },
        ],
    )

    logger.info(f"Sent {event_type.value} event to event bus {EVENT_BUS_NAME}:")
    logger.info(event_json)
    logger.info(f"{__name__} done.")
    return response
