import os
import logging
from libumccr.aws import libeb
from workflow_manager_proc.domain.event import wrsc, wru

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EventBridgePublishError(RuntimeError):
    """Raised when EventBridge accepts a request but rejects its event entry."""

    def __init__(self, message: str, failed_entries: list[dict] | None = None):
        super().__init__(message)
        self.failed_entries = failed_entries or []


def emit_wru_api_event(event: dict):
    """
    Validate the event dict against the WorkflowRunUpdate schema and emit it to EventBridge.
    """
    source = "orcabus.workflowmanagerapi"
    event_bus_name = os.environ.get("EVENT_BUS_NAME", None)

    if event_bus_name is None:
        raise ValueError("EVENT_BUS_NAME environment variable is not set.")

    validated = wru.WorkflowRunUpdate.model_validate(event)

    # Omit keys with value null: JSON schema marks optional fields as non-required string types,
    # not as nullable; emitting null violates the schema.
    detail_json = validated.model_dump_json(exclude_none=True)

    logger.info(f"Emitting WRU event to event bus {event_bus_name}: {event}")
    response = libeb.emit_event(
        {
            "Source": source,
            "DetailType": wru.WorkflowRunUpdate.__name__,
            "Detail": detail_json,
            "EventBusName": event_bus_name,
        }
    )

    logger.info(f"{__name__} done.")
    return response


def emit_wrsc_api_event(event: dict, attempt_count: int = 1):
    """Validate and emit a WorkflowRunStateChange created through the API."""
    source = "orcabus.workflowmanager"
    event_id = event.get("id", "unknown")
    workflow_run_id = event.get("orcabusId", "unknown")
    event_status = event.get("status", "unknown")

    try:
        event_bus_name = os.environ.get("EVENT_BUS_NAME", None)
        if event_bus_name is None:
            raise ValueError("EVENT_BUS_NAME environment variable is not set.")

        validated = wrsc.WorkflowRunStateChange.model_validate(event)
        detail_json = validated.model_dump_json(exclude_none=True)
        event_id = validated.id
        workflow_run_id = validated.orcabusId
        event_status = validated.status

        logger.info(
            "Emitting WRSC event: event_id=%s workflow_run_id=%s status=%s attempt=%s",
            event_id,
            workflow_run_id,
            event_status,
            attempt_count,
        )
        response = libeb.emit_event(
            {
                "Source": source,
                "DetailType": wrsc.WorkflowRunStateChange.__name__,
                "Detail": detail_json,
                "EventBusName": event_bus_name,
            }
        )

        failed_entry_count = response.get("FailedEntryCount", 0)
        if failed_entry_count:
            failed_entries = [
                {
                    "error_code": entry.get("ErrorCode"),
                    "error_message": entry.get("ErrorMessage"),
                }
                for entry in response.get("Entries", [])
                if entry.get("ErrorCode") or entry.get("ErrorMessage")
            ]
            logger.error(
                "EventBridge rejected WRSC event entry: event_id=%s workflow_run_id=%s status=%s attempt=%s failed_entry_count=%s failed_entries=%s",
                event_id,
                workflow_run_id,
                event_status,
                attempt_count,
                failed_entry_count,
                failed_entries,
            )
            raise EventBridgePublishError(
                f"EventBridge rejected {failed_entry_count} WRSC event entry: {failed_entries}",
                failed_entries=failed_entries,
            )

        logger.info(
            "WRSC event emitted: event_id=%s workflow_run_id=%s status=%s attempt=%s",
            event_id,
            workflow_run_id,
            event_status,
            attempt_count,
        )
        return response
    except Exception:
        logger.exception(
            "Failed to emit WRSC event: event_id=%s workflow_run_id=%s status=%s attempt=%s",
            event_id,
            workflow_run_id,
            event_status,
            attempt_count,
        )
        raise
