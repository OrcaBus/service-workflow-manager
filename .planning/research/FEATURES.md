# Feature Landscape

**Domain:** Workflow orchestration context metadata — RunContext model extension
**Researched:** 2026-03-23
**Confidence:** HIGH (based directly on production codebase, schemas, and PROJECT.md requirements)

---

## Current State Baseline

The system today represents execution environment context as two opaque strings:

- `computeEnv: "clinical"` — bare string, no platform, no project/space encoding
- `storageEnv: "research"` — bare string, same problem

These strings are the `name` field on a `RunContext(name, usecase)` record. The `name` is implicitly a compound encoding of platform + project/space (e.g. `"icav2-prod-projectX"`), but nothing enforces this or makes it queryable. The same structural problem exists in the parallel `AnalysisContext` model, which is byte-for-byte identical.

All four event schemas (WRU, WRSC, ARU, ARSC) carry `computeEnv: string | null` and `storageEnv: string | null`. The WRSC hash includes the raw `computeEnv` and `storageEnv` strings as hash inputs.

The `Workflow` model already has a typed `ExecutionEngine` enum (`ICA`, `SEQERA`, `AWS_BATCH`, `AWS_ECS`, `AWS_EKS`, `Unknown`) — but this lives on the pipeline definition, not on the individual run's execution environment.

---

## Table Stakes

Features that are essential for cross-platform tracking. Missing = the system cannot distinguish runs across platforms and project spaces.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Typed `platform` field on `RunContext` | Enables filtering `WHERE platform = 'ICAV2'`; currently impossible without parsing opaque name strings | Low | Use `TextChoices` — reuse same enum values as `ExecutionEngine` (ICA, SEQERA, AWS_BATCH, AWS_ECS). Extend, don't invent. |
| `data` JSONField on `RunContext` for platform-specific properties | ICA needs `projectId`; Seqera needs `workspaceId`; AWS Batch needs `jobQueueArn` + `account`. One schema cannot express all three as typed columns. | Low | PostgreSQL JSONField, validated at service layer not DB layer. See platform-specific shapes below. |
| `EXECUTION_MODE` use case on `RunContextUseCase` | External scheduler decides manual vs automated — needs to be trackable per run, not inferred from source field | Low | Add `EXECUTION_MODE = "EXECUTION_MODE"` to `RunContextUseCase.TextChoices`. The `name` field holds `"manual"` or `"automated"`. |
| Structured context objects in WRU/WRSC event schemas | Bare `computeEnv: string` cannot express platform + project/space to downstream consumers. Scheduler must be able to say: ICA, project X, not just `"icav2-prod-X"` | Medium | Replace `computeEnv: string` with `computeEnv: { name: string, platform: string, data: object }`. Same for `storageEnv` and new `executionMode`. |
| Structured context objects in ARU/ARSC event schemas | ARU already has `computeEnv`/`storageEnv` bare strings; the ARU path uses `RunContext.objects.get()` — it will break if `name` is no longer the full identifier | Medium | Align ARU schema with WRU schema: same `{ name, platform, data }` shape for all three context fields. |
| `AnalysisContext` retirement and unification into `RunContext` | Two structurally identical models (prefixes `rnx` vs `anx`) will compound in complexity with every future extension. AnalysisRun already references `RunContext` not `AnalysisContext` for its `contexts` M2M. | Medium | Drop `AnalysisContext` table. Migration: any existing `AnalysisContext` records must be migrated to `RunContext` with matching `(name, usecase)`. Confirm all FK/M2M references updated. |
| WRSC hash updated to include structured context data | Current WRSC hash inputs include `computeEnv` and `storageEnv` as raw strings. After schema change, these become structured objects — hash inputs must change to `platform + RFC8785 canonical hash of data` | Low | Mechanical change in `get_wrsc_hash()`. Same pattern already used for payload deduplication. |

---

## Differentiators

Features that provide richer operational capability. Not required for basic tracking, but valuable once the platform surface grows.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `ExecutionPolicy` model (approval gates, workflow eligibility) | Decouples operational constraints from execution environment. An AnalysisRun's approved workflows and approval state are orthogonal to where it runs. | Medium-High | PROJECT.md explicitly scopes this OUT of this milestone — it is a separate phase after RunContext extension lands. Do not conflate with `RunContext`. |
| REST API filter on `RunContext.platform` | Enables queries like "all WorkflowRuns on SEQERA this week" for operational monitoring | Low | Straightforward DRF `FilterSet` extension once `platform` column exists. |
| `RunContext.status` lifecycle (`ACTIVE`/`INACTIVE`) | Already exists. Allows retiring an environment (e.g. a decommissioned ICA project) without deleting records. | Already present | No change needed here. |
| Canonical platform-specific `data` schemas as documentation | Teams using ICA, Seqera, or AWS Batch need to know what keys to put in `data`. A documented JSON Schema per platform (even informal) prevents opaque blobs accumulating. | Low | Not a code feature — a schema doc artifact. Important for scheduler coordination. |
| ARSC hash updated consistently with WRSC | Once ARSC includes structured context fields, the `get_arsc_hash()` function needs the same structured hash treatment as WRSC | Low | Follows mechanically from WRSC change. Currently ARSC hash includes `computeEnv` and `storageEnv` as raw strings. |

---

## Anti-Features

Features to explicitly NOT build in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Per-platform DB tables (IcaContext, SeqeraContext, AwsBatchContext) | Requires schema migration for every new platform; violates open/closed. The whole point of this milestone is to avoid this. | `data: JSONField` with platform-validated at service layer, not DB layer. |
| Free-text `platform` string (no enum) | Loses the queryability and self-documentation that motivates the change from `name` alone. `"ICAV2"` vs `"icav2"` vs `"ICA"` would all be valid, breaking filters. | `TextChoices` enum. Extend when a new platform is onboarded, not ad hoc. |
| Multiple COMPUTE or STORAGE contexts per run | PROJECT.md explicitly out-of-scopes this: "stays one COMPUTE, one STORAGE, one EXECUTION_MODE per run." Adding M2M cardinality changes would complicate the hash function and downstream consumer contracts. | Enforce one-per-usecase at service layer, not DB layer (already the pattern). |
| Backward-compatible event processing for old bare-string `computeEnv`/`storageEnv` | PROJECT.md explicitly: "external scheduler is responsible for migrating to structured objects." Building a dual-parsing path inside the service creates permanent tech debt and masks coordinator errors. | The legacy Lambda handler pattern can be reused if needed, but this is a scheduler-side concern. |
| `ExecutionPolicy` in this milestone | Approval gates, workflow eligibility rules — these are explicitly deferred. Adding them now would block RunContext work behind a larger design problem. | Separate phase after RunContext extension ships. |
| Changing `AnalysisRunState` lifecycle (beyond DRAFT → READY) | Out of scope. AnalysisRun state machine is intentionally minimal. | Leave state machine unchanged. |

---

## Feature Dependencies

```
platform field on RunContext
  → data JSONField on RunContext (both land together — one migration)
  → EXECUTION_MODE use case (additive to same migration)
  → AnalysisContext retirement (can only safely unify once RunContext schema is settled)

Structured context objects in JSON Schema files (WRU/WRSC/ARU/ARSC)
  → datamodel-codegen re-run → new Pydantic models
  → Service layer updates (establish_workflow_run_contexts, establish_analysis_run_contexts)
  → WRSC hash update (inputs change from raw strings to structured data)
  → ARSC hash update (same reason)

AnalysisContext retirement
  → depends on: platform + data fields added to RunContext (migration chain)
  → depends on: all AnalysisRun.contexts M2M references already point to RunContext (verified: they do)
  → requires: data migration from AnalysisContext table → RunContext table
```

---

## Platform-Specific `data` Shapes

These are the known platform-specific keys that the `data` JSONField must accommodate. Based on evidence from `WRU_max.json` (ICA payload data currently carries `projectId`, `executionId`), and the `ExecutionEngine` enum values in `workflow.py`.

**ICA (ICAV2)**
```json
{
  "projectId": "bxxxxxxxx-dxxx-4xxxx-adcc-xxxxxxxxx",
  "pipelineId": "optional-pipeline-id"
}
```

**SEQERA**
```json
{
  "workspaceId": "123456789",
  "workspaceName": "optional-human-readable"
}
```

**AWS_BATCH**
```json
{
  "jobQueue": "arn:aws:batch:ap-southeast-2:123456789012:job-queue/my-queue",
  "jobDefinition": "optional-job-definition-name"
}
```

**Storage contexts** (STORAGE use case, platform-specific)
```json
{
  "bucketName": "my-bucket",
  "prefix": "optional/path/prefix",
  "awsAccountId": "123456789012"
}
```

Note: The `data` schema is not enforced at the DB layer. It is validated at service layer when processing events. For ICA, `projectId` is the minimum viable required field; for Seqera, `workspaceId`. AWS Batch requires `jobQueue`.

---

## Structured Context Object Shape (Event Schema)

The target schema for all three context fields in WRU/WRSC/ARU/ARSC (replacing bare `string`):

```json
{
  "name": "string (human-readable label, still used for RunContext uniqueness alongside platform)",
  "platform": "string (enum: ICAV2 | SEQERA | AWS_BATCH | AWS_ECS)",
  "data": {}
}
```

This maps cleanly to the new `RunContext(name, usecase, platform, data)` model. The service layer creates or retrieves a `RunContext` by `(name, usecase, platform)` on event receipt.

**WRSC hash inputs after change:**
- Old: `keywords.append(out_wrsc.computeEnv)` — raw string
- New: `keywords.append(out_wrsc.computeEnv.platform)` + `keywords.append(rfc8785_hash(out_wrsc.computeEnv.data))`

This preserves the deduplication guarantee while covering the richer structured fields.

---

## MVP Recommendation

This milestone is well-scoped in PROJECT.md. The minimum viable feature set in order:

1. **`RunContext` model extension** — add `platform` (TextChoices) + `data` (JSONField) + `EXECUTION_MODE` use case. One migration.
2. **`AnalysisContext` retirement** — data migration + drop table + update any remaining `AnalysisContext` references. Best done in same migration as (1).
3. **JSON Schema files updated** — `computeEnv`, `storageEnv`, `executionMode` become structured objects in WRU/WRSC/ARU/ARSC schemas.
4. **Pydantic models regenerated** via `datamodel-codegen`.
5. **Service layer updated** — `establish_workflow_run_contexts()` and its ARU equivalent parse structured objects, not bare strings.
6. **Hash functions updated** — `get_wrsc_hash()` and `get_arsc_hash()` use `platform + data_hash`.

Defer: `ExecutionPolicy` model — separate milestone per PROJECT.md.

---

## Event Schema Patterns Observed

The codebase uses a consistent EventBridge envelope pattern:

```
AWSEvent {
  detail-type: string     (event type discriminator for EventBridge rules)
  source: string          (producer identity — used for rule filtering)
  detail: <EventSchema>   (domain-specific payload)
}
```

All schemas are JSON Schema draft-04 files. The Pydantic models are code-generated — no hand-authoring. Schema files are the contract source of truth. Changes to event fields require: (1) edit JSON Schema, (2) run `datamodel-codegen`, (3) commit generated Pydantic models.

**Deduplication ID pattern:**
- WRSC and ARSC both have an `id` field computed as MD5 over a sorted list of key field values
- This is computed at emit time, not stored in DB
- After structured context fields land: the hash inputs must be updated to use platform + canonical JSON hash of `data` (not raw object string representation)

**Field optionality pattern:**
- Inbound events (WRU, ARU): context fields are `Optional[str]` — runs may have no context at all
- Outbound events (WRSC, ARSC): context fields are also `Optional` — same contract for downstream consumers
- The structured context object should preserve this: `Optional[ContextObject]`, not a required field

---

## Sources

All findings are HIGH confidence. Derived directly from:

- `/app/workflow_manager/models/run_context.py` — current `RunContext` model
- `/app/workflow_manager/models/analysis_context.py` — duplicate `AnalysisContext` model
- `/app/workflow_manager/models/workflow.py` — existing `ExecutionEngine` enum
- `/app/workflow_manager_proc/domain/event/wru.py` — current WRU Pydantic model
- `/app/workflow_manager_proc/domain/event/wrsc.py` — current WRSC Pydantic model
- `/app/workflow_manager_proc/domain/event/aru.py` — current ARU Pydantic model
- `/app/workflow_manager_proc/domain/event/arsc.py` — current ARSC Pydantic model
- `/app/workflow_manager_proc/services/workflow_run.py` — context establishment logic and hash function
- `/app/workflow_manager_proc/services/analysis_run.py` — ARU context logic and ARSC hash function
- `/docs/events/WorkflowRunUpdate/WorkflowRunUpdate.schema.json` — canonical WRU JSON Schema
- `/docs/events/WorkflowRunUpdate/examples/WRU__example*.json` — real event shapes
- `/docs/events/WorkflowRunStateChange/WorkflowRunStateChange.schema.json` — canonical WRSC JSON Schema
- `/docs/events/AnalysisRunUpdate/AnalysisRunUpdate.schema.json` — canonical ARU JSON Schema
- `.planning/PROJECT.md` — requirements, out-of-scope declarations, key decisions
- `.planning/codebase/ARCHITECTURE.md` — system architecture and data flow
