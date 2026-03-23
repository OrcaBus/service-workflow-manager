# service-workflow-manager

## What This Is

An event-driven Django microservice within the OrcaBus platform that tracks the lifecycle and state of workflow runs and analysis runs across heterogeneous execution environments (ICA, Seqera, AWS Batch). It receives `WorkflowRunUpdate` and `AnalysisRunUpdate` events from an external scheduler via EventBridge, persists state transitions with deduplication, and emits downstream `WorkflowRunStateChange` / `AnalysisRunStateChange` events. A REST API exposes run history and limited write operations.

## Core Value

Accurate, deduplicated state tracking of workflow and analysis runs regardless of which execution platform or project space they ran on.

## Requirements

### Validated

- ✓ WorkflowRun lifecycle tracking (DRAFT → READY → RUNNING → SUCCEEDED / FAILED / ABORTED) with state deduplication — existing
- ✓ AnalysisRun lifecycle tracking (DRAFT → READY) — existing
- ✓ Library and Readset associations on WorkflowRun — existing
- ✓ Execution environment context (compute + storage) attached to WorkflowRun via RunContext — existing
- ✓ AnalysisRun context, library, and readset associations — existing
- ✓ REST API for querying WorkflowRuns, AnalysisRuns, Workflows, Libraries, Readsets, RunContexts — existing
- ✓ WorkflowRun rerun action (rnasum) — existing
- ✓ Legacy WRSC event processing for backward compatibility — existing
- ✓ EventBridge event emission after state transitions — existing

### Active

- [ ] `RunContext` enriched with `platform` (extensible enum: ICAV2, SEQERA, AWS_BATCH, AWS_ECS) and `data` (JSONField for platform-specific properties)
- [ ] `RunContextUseCase` extended with `EXECUTION_MODE` (manual / automated) alongside existing COMPUTE and STORAGE
- [ ] `AnalysisContext` model retired and unified into `RunContext` — one model for all context use cases across WorkflowRun and AnalysisRun
- [ ] WRU and WRSC event schemas extended: `computeEnv`, `storageEnv`, and `executionMode` evolve from bare strings to structured context objects (`{ name, platform, data }`)
- [ ] ARU event schema extended with context fields aligned with WRU (`computeEnv`, `storageEnv`, `executionMode`)
- [ ] WRSC event hash updated to include structured context data (platform + RFC8785 canonical hash of `data`)
- [ ] New `ExecutionPolicy` model for operational constraints on AnalysisRun (approval gates, workflow eligibility) — separate from RunContext

### Out of Scope

- ExecutionPolicy model detailed design — scope is established but implementation is a separate phase after RunContext extension lands
- Changing WorkflowRun context cardinality — stays one COMPUTE, one STORAGE, one EXECUTION_MODE per run
- Backward-compatible event processing for old bare-string `computeEnv`/`storageEnv` — external scheduler is responsible for migrating to structured objects; legacy Lambda handler pattern can be reused if needed

## Context

**Existing architecture:** Event-driven dual-surface service — EventBridge Lambda handlers for async event processing + WSGI Lambda for REST API. All state persists in PostgreSQL (Aurora). Django ORM shared across both surfaces. Three Lambda event handlers: WRU (new schema), ARU (new schema), legacy WRSC.

**RunContext today:** A flat `(name, usecase)` model where `name` is an opaque compound string (e.g. `"icav2-prod-projectX"`) that implicitly encodes platform and project/space. The model is duplicated as `AnalysisContext` (structurally identical, separate table).

**Driver for this work:** A more complex service environment is emerging. An external scheduler decides which workflows run and where, attaching context information to WRU events. Multiple compute platforms (ICA, Seqera, AWS Batch) and multiple project spaces per platform need to be expressed distinctly — not as opaque strings. AnalysisRuns also require operational constraint context (approval, eligibility) that is orthogonal to execution environment.

**Event schema constraint:** WRU/WRSC/ARU schemas are code-generated from JSON Schema files via `datamodel-code-generator`. Schema changes require regenerating Pydantic models and coordinating with upstream event producers (the external scheduler).

**Codebase map:** `.planning/codebase/` — generated 2026-03-23.

## Constraints

- **Compatibility**: Event schema changes are a cross-service contract — upstream scheduler must be coordinated with
- **Tech stack**: Python 3.12, Django 5.2, Pydantic v2; event models code-generated from JSON Schema
- **Backward compatibility**: Existing `RunContext` records and API consumers must not break; migration path required for `AnalysisContext` → `RunContext` unification
- **Atomicity**: All DB writes in Lambda handlers are `@transaction.atomic`; schema changes must preserve this guarantee

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| `platform` as extensible enum (`TextChoices`) not free string | Queryable, validated, self-documenting; known platforms (ICA, Seqera, Batch) warrant typed values | — Pending |
| `AnalysisContext` unified into `RunContext` | Structurally identical models; eliminates duplication that would compound with every future extension | — Pending |
| Event schema uses structured context objects, not bare strings | Platform + project/space cannot be expressed in a single opaque string; scheduler needs to pass structured data | — Pending |
| ARU context fields aligned with WRU | Consistency over custom design; AnalysisRun context is still one compute + one storage + one execution mode | — Pending |
| `ExecutionPolicy` as separate model from `RunContext` | Operational constraints (approval, eligibility) are orthogonal to execution environment — many exceptions prevent coupling | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-23 after initialization*
