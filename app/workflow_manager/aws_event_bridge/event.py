import os
import logging
from libumccr.aws import libeb
from workflow_manager_proc.domain.event import wru

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def emit_wru_api_event(event: dict):
    """
    Validate the event dict against the WorkflowRunUpdate schema and emit it to EventBridge.
    """
    source = "orcabus.workflowmanagerapi"
    event_bus_name = os.environ.get("EVENT_BUS_NAME", None)

    if event_bus_name is None:
        raise ValueError("EVENT_BUS_NAME environment variable is not set.")

    validated = wru.WorkflowRunUpdate.model_validate(event)

    logger.info(f"Emitting WRU event to event bus {event_bus_name}: {event}")
    response = libeb.emit_event({
        'Source': source,
        'DetailType': wru.WorkflowRunUpdate.__name__,
        'Detail': validated.model_dump_json(),
        'EventBusName': event_bus_name,
    })

    logger.info(f"{__name__} done.")
    return response
