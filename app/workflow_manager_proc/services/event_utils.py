import boto3
import logging
import rfc8785
import hashlib
from enum import Enum
from workflow_manager_proc.domain.event import arsc, wrsc

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

client = boto3.client('events', region_name='ap-southeast-2')
SOURCE = "orcabus.workflowmanager"


class EventType(Enum):
    WRSC = "WorkflowRunStateChange"
    ARSC = "AnalysisRunStateChange"


def emit_event(event_type: EventType, event_bus: str, event_json):
    """
    Parameters:
        event_type: the type of event to emit using EventType
        event_bus: the name of the event bus to emit the message to
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
                'EventBusName': event_bus,
            },
        ],
    )

    logger.info(f"Sent {event_type.value} event to event bus {event_bus}:")
    logger.info(event_json)
    logger.info(f"{__name__} done.")
    return response


def hash_payload_data(data: dict) -> str:
    """
    Generates a unique hash for the JSON represented as dict.
    First generates the canonical JSON following RFC8785. Then calculates the SHA256 (hex) digest.
    Args:
        data: the dict representing the JSON payload. Has to be JSON serializable.

    Returns: a hash of the input.

    """
    data_canonical = rfc8785.dumps(data)
    data_hash = hashlib.sha256(data_canonical).hexdigest()
    return data_hash
