from enum import Enum
from typing import List


class Status(Enum):
    DRAFT = "DRAFT", ["DRAFT"]
    READY = "READY", ["READY"]
    RUNNING = "RUNNING", ["RUNNING", "IN_PROGRESS"]
    SUCCEEDED = "SUCCEEDED", ["SUCCEEDED", "SUCCESS"]
    FAILED = "FAILED", ["FAILED", "FAILURE", "FAIL"]
    ABORTED = "ABORTED", ["ABORTED"]
    CANCELLED = "CANCELLED", ["CANCELLED", "CANCELED"]
    RESOLVED = "RESOLVED", ["RESOLVED"]
    DEPRECATED = "DEPRECATED", ["DEPRECATED"]

    def __init__(self, convention: str, aliases: List[str]):
        self.convention = convention
        self.aliases = aliases

    def __str__(self):
        return self.convention

    @staticmethod
    def get_convention(status: str):
        # enforce upper case convention
        status = status.upper()
        status = status.replace("-", "_")
        # TODO: handle other characters?
        for s in Status:
            if status in s.aliases:
                return s.convention

        # retain all uncontrolled states
        return status

    @staticmethod
    def is_supported(status: str) -> bool:
        # enforce upper case convention
        status = status.upper()
        for s in Status:
            if status in s.aliases:
                return True
        return False

    @staticmethod
    def terminal_conventions() -> tuple[str, ...]:
        return (
            Status.SUCCEEDED.convention,
            Status.FAILED.convention,
            Status.ABORTED.convention,
            Status.CANCELLED.convention,
            Status.RESOLVED.convention,
            Status.DEPRECATED.convention,
        )

    @staticmethod
    def is_terminal(status: str) -> bool:
        status = Status.get_convention(status)
        return status in Status.terminal_conventions()

    @staticmethod
    def is_draft(status: str) -> bool:
        # enforce upper case convention
        status = status.upper()
        return status in Status.DRAFT.aliases

    @staticmethod
    def is_running(status: str) -> bool:
        # enforce upper case convention
        status = status.upper()
        return status in Status.RUNNING.aliases

    @staticmethod
    def is_ready(status: str) -> bool:
        # enforce upper case convention
        status = status.upper()
        return status in Status.READY.aliases

    @staticmethod
    def is_resolved(status: str) -> bool:
        # enforce upper case convention
        status = status.upper()
        return status in Status.RESOLVED.aliases
