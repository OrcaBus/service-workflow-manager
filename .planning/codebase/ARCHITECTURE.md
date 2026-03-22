# Architecture
> Generated: 2026-03-23
> Focus: Patterns, layers, data flow, key design decisions, module boundaries, end-to-end system behavior

## Pattern Overview

**Overall:** Event-driven microservice with dual ingress surfaces — AWS EventBridge (async event processing via Lambda) and REST API (HTTP, read-mostly). Uses a Django ORM core shared across both surfaces.

**Key Characteristics:**
- Two co-deployed Django apps: `workflow_manager` (API + models + DB) and `workflow_manager_proc` (event processing Lambdas)
- All persistent state lives in PostgreSQL (AWS RDS Aurora); no in-memory or cache layer
- Emits downstream events back onto the same EventBridge bus after persisting state changes
- OrcaBus-scoped unique IDs with type-prefixed primary keys (`wfr`, `wfl`, `stt`, `pld`, `anr`, `ana`, etc.)
- Three Lambda event handlers, one WSGI API Lambda, one migration Lambda — all deployed as separate Python functions sharing a common base layer

---

## Layers

**Domain Models (`app/workflow_manager/models/`):**
- Purpose: Persistent data representation; single source of truth for all entities
- All models inherit `OrcaBusBaseModel` (`app/workflow_manager/models/base.py`)
- `OrcaBusBaseModel.save()` always calls `full_clean()` then `refresh_from_db()` to enforce validation and reload custom field annotations
- Uses custom `OrcaBusIdField` (`app/workflow_manager/fields.py`) as primary key with type-prefixed IDs
- Custom `OrcaBusBaseManager` provides `get_by_keyword()` for multi-value OR filtering used by viewsets
- Depends on: PostgreSQL via Django ORM
- Used by: viewsets (read), proc services (read/write)

**API Layer (`app/workflow_manager/viewsets/`, `app/workflow_manager/urls/`, `app/workflow_manager/serializers/`):**
- Purpose: Expose read-only REST API; limited write operations for Workflow and WorkflowRunAction
- Entry point: `app/api.py` → `serverless_wsgi.handle_request` → Django WSGI → `workflow_manager.urls.base`
- `BaseViewSet` is read-only (`ReadOnlyModelViewSet`) — most resources are GET-only
- `WorkflowViewSet` extends `PostOnlyViewSet` (GET + POST, no updates)
- `WorkflowRunActionViewSet` provides POST `/workflowrun/{id}/rerun` and GET `/workflowrun/{id}/validate_rerun_workflows`
- API is camelCase (via `djangorestframework-camel-case` middleware)
- Pagination: `StandardResultsSetPagination` on all lists
- OpenAPI schema generated at `/schema/openapi.json` via `drf-spectacular`
- Depends on: Domain models, serializers, AWS EventBridge (for rerun action)
- Used by: External HTTP clients via API Gateway

**Event Processing Layer (`app/workflow_manager_proc/`):**
- Purpose: React to EventBridge events, persist state, emit downstream events
- Three Lambda handlers, each a thin wrapper that delegates to services
- `domain/event/` contains Pydantic models (`wru.py`, `wrsc.py`, `aru.py`, `arsc.py`) — code-generated from JSON Schema
- `services/` contains business logic separated by entity (workflow_run, analysis_run)
- All service functions decorated with `@transaction.atomic`
- Depends on: Domain models (shared Django ORM), AWS boto3 EventBridge client, `rfc8785` for canonical JSON hashing
- Used by: AWS Lambda (triggered by EventBridge Rules)

**Infrastructure Layer (`infrastructure/stage/`):**
- Purpose: CDK stack defining all Lambda functions, EventBridge rules, API Gateway routes, IAM roles
- Written in TypeScript (AWS CDK)
- `stack.ts` defines the `WorkflowManagerStack` with all resources
- `schema.ts` defines EventBridge schema registry publishing
- `lambda-migration/` handles automatic DB migration on deployment

---

## Data Flow

**WorkflowRunUpdate (WRU) Event Flow:**
1. External service publishes `WorkflowRunUpdate` event to EventBridge main bus (source: anything except `orcabus.workflowmanager`)
2. EventBridge Rule `EventRule2` matches `detail-type: WorkflowRunUpdate` → triggers `HandleWruEvent` Lambda
3. `app/workflow_manager_proc/lambdas/handle_wru_event.py::handler()` unpacks `AWSEvent` envelope → extracts `WorkflowRunUpdate`
4. Delegates to `app/workflow_manager_proc/services/workflow_run.py::create_workflow_run()`
5. Inside `_create_workflow_run()` (atomic transaction):
   - Looks up or raises for `Workflow` by `orcabusId`
   - Gets or creates `WorkflowRun` by `portalRunId`
   - Establishes Library and Readset associations (only at creation time for libraries)
   - Establishes RunContext associations (computeEnv / storageEnv)
   - Calls `WorkflowRunUtil.transition_to(new_state)` — state machine guard
   - State machine checks hash of new state vs current state to prevent duplicates
6. If state transition succeeds: maps result to `WorkflowRunStateChange` (WRSC) Pydantic object
7. Emits WRSC event back to EventBridge bus via `emit_event()` with source `orcabus.workflowmanager`

**AnalysisRunUpdate (ARU) Event Flow:**
1. External service publishes `AnalysisRunUpdate` (status DRAFT or READY) to EventBridge
2. EventBridge Rule `EventRuleARU` matches `detail-type: AnalysisRunUpdate` → triggers `HandleAruEvent` Lambda
3. `app/workflow_manager_proc/lambdas/handle_aru_event.py::handler()` unpacks event
4. Branches on status:
   - `DRAFT` → `create_analysis_run()`: creates `AnalysisRun` + `AnalysisRunState(DRAFT)` + library/readset associations, emits ARSC event
   - `READY` → `finalise_analysis_run()`: validates existing `AnalysisRun`, transitions to READY state, emits ARSC event, then calls `_create_workflow_runs_for_analysis_run()` which auto-generates DRAFT `WorkflowRun` records (one per workflow defined in the linked `Analysis`)
5. Each auto-generated WorkflowRun triggers its own WRU processing path internally

**Legacy WRSC Event Flow (Backward Compatibility):**
1. External service publishes old-schema `WorkflowRunStateChange` (with `workflowName` + `workflowVersion` at top-level)
2. EventBridge Rule `EventRule` matches `detail-type: WorkflowRunStateChange` (source not `orcabus.workflowmanager`, must have `workflowName` and `workflowVersion`)
3. `handle_wrsc_event_legacy.py` processes using `services/workflow_run_legacy.py`

**REST API → Rerun Flow:**
1. HTTP POST `/api/v1/workflowrun/{id}/rerun` → `WorkflowRunActionViewSet.rerun()`
2. Validates workflow name is in `AllowedRerunWorkflow` enum (currently only `rnasum`)
3. Constructs new EB event detail with a fresh `portal_run_id` and overridden payload
4. Emits legacy WRSC event via `emit_wrsc_api_event()` with source `orcabus.workflowmanagerapi`

---

## State Machine

`WorkflowRunUtil.transition_to()` in `app/workflow_manager/models/utils.py` enforces transitions:

| Current State | Allowed Next States |
|---------------|---------------------|
| None (new)    | DRAFT (preferred), any (with warning) |
| DRAFT         | DRAFT (payload update), READY |
| READY         | Any non-DRAFT, non-READY |
| RUNNING       | Any non-DRAFT, non-READY; RUNNING only if >1 hour since last RUNNING |
| Terminal (SUCCEEDED, FAILED, ABORTED) | None (blocked) |
| Other         | Any not previously seen |

Duplicate detection: `StateUtil.create_state_hash(state)` computes MD5 over `status + comment + payload_ref_id`. Same hash as current state → reject silently.

**AnalysisRunState** uses simpler two-step: DRAFT → READY only, enforced by assertion in `_finalise_analysis_run()`.

---

## Key Abstractions

**Workflow:**
- Represents a versioned pipeline definition (name + version + code_version + execution_engine)
- Unique constraint: `(name, version, code_version, execution_engine)`
- Has a `validation_state` (UNVALIDATED / VALIDATED / DEPRECATED / FAILED)
- Execution engines: ICA, SEQERA, AWS_BATCH, AWS_ECS, AWS_EKS, Unknown
- File: `app/workflow_manager/models/workflow.py`

**WorkflowRun:**
- Represents one execution of a Workflow
- Identified by `portal_run_id` (unique, human-readable: `YYYYMMDD` + 8-char UUID)
- Links to: one `Workflow`, optional `AnalysisRun`, many `Library` (via `LibraryAssociation`), many `Readset`, many `RunContext`
- State history kept in separate `State` model (one-to-many)
- File: `app/workflow_manager/models/workflow_run.py`

**State:**
- Append-only state history for a WorkflowRun
- Fields: `status`, `timestamp`, optional `comment`, optional `Payload` FK
- Unique constraint: `(workflow_run, status, timestamp)`
- File: `app/workflow_manager/models/state.py`

**Payload:**
- Stores arbitrary JSON data attached to a State
- Deduplicated by `payload_ref_id` (SHA-256 of RFC8785 canonical JSON)
- File: `app/workflow_manager/models/payload.py`

**Analysis:**
- Groups multiple Workflows into a logical analysis pipeline
- Links to: many `Workflow`, many `AnalysisContext`
- When an AnalysisRun reaches READY, one WorkflowRun is auto-created per linked Workflow
- File: `app/workflow_manager/models/analysis.py`

**AnalysisRun:**
- One execution of an Analysis
- Separate state model: `AnalysisRunState` (DRAFT → READY only)
- No Payload attached to AnalysisRunState (unlike WorkflowRun State)
- File: `app/workflow_manager/models/analysis_run.py`

**RunContext:**
- Compute or storage environment descriptor (e.g., specific AWS account/environment)
- Unique by `(name, usecase)` where usecase is COMPUTE or STORAGE
- File: `app/workflow_manager/models/run_context.py`

**Status Conventions:**
- `Status` enum in `app/workflow_manager/models/common.py` normalizes incoming status strings via aliases
- DRAFT aliases: DRAFT, INITIAL, CREATED
- RUNNING aliases: RUNNING, IN_PROGRESS
- SUCCEEDED aliases: SUCCEEDED, SUCCESS
- FAILED aliases: FAILED, FAILURE, FAIL
- ABORTED aliases: ABORTED, CANCELLED, CANCELED

---

## Event Schema Architecture

Two families of event schemas coexist:

**New schema (Pydantic, code-generated from JSON Schema):**
- `WorkflowRunUpdate` (WRU) — inbound: `app/workflow_manager_proc/domain/event/wru.py`
- `WorkflowRunStateChange` (WRSC) — outbound: `app/workflow_manager_proc/domain/event/wrsc.py`
- `AnalysisRunUpdate` (ARU) — inbound: `app/workflow_manager_proc/domain/event/aru.py`
- `AnalysisRunStateChange` (ARSC) — outbound: `app/workflow_manager_proc/domain/event/arsc.py`

**Legacy schema (marshaller-based):**
- `app/workflow_manager/aws_event_bridge/executionservice/workflowrunstatechange/` — inbound WRSC from external execution services
- `app/workflow_manager/aws_event_bridge/workflowmanager/workflowrunstatechange/` — outbound (used by rerun API action)

**Event ID / Deduplication:**
- WRSC events have an `id` field computed as MD5 of key fields (version, orcabusId, portalRunId, workflowRunName, status, workflow.orcabusId, payload.refId, library IDs, readset IDs, computeEnv, storageEnv)
- ARSC events use similar MD5 hash
- Payload data deduplication: SHA-256 of RFC8785 canonical JSON stored as `payload_ref_id`

---

## Entry Points

**API Lambda:** `app/api.py::handler` — WSGI bridge via `serverless_wsgi`, routes all HTTP traffic through Django

**Migration Lambda:** `app/migrate.py::handler` — runs `manage.py migrate` on deploy

**WRU Event Lambda:** `app/workflow_manager_proc/lambdas/handle_wru_event.py::handler`

**ARU Event Lambda:** `app/workflow_manager_proc/lambdas/handle_aru_event.py::handler`

**Legacy WRSC Lambda:** `app/workflow_manager_proc/lambdas/handle_wrsc_event_legacy.py::handler`

---

## Error Handling

**Strategy:** Raise exceptions to fail the Lambda invocation (allowing EventBridge retry). API errors use DRF standard error responses.

**Patterns:**
- Missing required records (Workflow, Analysis): raise exception — triggers Lambda retry
- Duplicate/unchanged state: return `False` from `transition_to()` — logged, no event emitted, Lambda succeeds
- Terminal state transition attempt: return `False` — silently ignored
- Rerun duplication: raises `RerunDuplicationError` → API returns HTTP 400
- State hash mismatch on payload: `assert` raises `AssertionError` → Lambda fails
- Stale events (timestamp earlier than current state): return `False` — silently ignored

---

## Cross-Cutting Concerns

**Logging:** Python `logging` module, console handler, INFO level by default. Each Lambda handler sets `logging.INFO` explicitly.

**Validation:** `OrcaBusBaseModel.save()` always calls `full_clean()`. Pydantic validates inbound event shapes at Lambda entry. Status strings normalized via `Status.get_convention()`.

**Authentication:** REST API uses Token authentication (`TokenAuthentication`). Rerun endpoint additionally requires Cognito JWT via API Gateway authorizer. Event Lambda handlers have no auth (protected by IAM/EventBridge policy).

**Tracing:** AWS X-Ray SDK integrated via Django middleware (`XRayMiddleware`). Disabled by default; enabled via `AWS_XRAY_SDK_ENABLED=true` env var.

**CORS:** Open (`CORS_ORIGIN_ALLOW_ALL = True`) with added AWS auth headers.
