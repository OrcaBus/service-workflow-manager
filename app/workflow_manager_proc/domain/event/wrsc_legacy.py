"""
Pydantic models for the legacy WorkflowRunStateChange (WRSC) event format.

Legacy events use flat fields (workflowName, workflowVersion, linkedLibraries)
rather than the nested structure of the current WRSC/WRU schemas.

This replaces the deleted executionservice marshaller module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LibraryRecord(BaseModel):
    libraryId: str
    orcabusId: str


class Payload(BaseModel):
    refId: str | None = None
    version: str
    data: dict[str, Any]


class WorkflowRunStateChange(BaseModel):
    portalRunId: str
    executionId: str | None = None
    timestamp: datetime
    status: str
    workflowName: str | None = None
    workflowVersion: str | None = None
    workflowRunName: str
    linkedLibraries: list[LibraryRecord] | None = None
    payload: Payload | None = None


class AWSEvent(BaseModel):
    id: str | None = None
    region: str | None = None
    resources: list[str] | None = None
    source: str
    time: datetime | None = None
    version: str | None = None
    account: str | None = None
    detail_type: str = Field(..., alias="detail-type")
    detail: WorkflowRunStateChange
