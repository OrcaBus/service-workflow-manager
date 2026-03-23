# Architecture Patterns

**Domain:** Event-driven Django microservice — RunContext extension, model unification, event schema evolution
**Researched:** 2026-03-23
**Confidence:** HIGH — based on direct codebase analysis, no training-data speculation

---

## Recommended Architecture

The milestone involves four interconnected changes. The recommended architecture treats them as a layered build where each layer has a safe rollback point before the next begins.

```
Layer 1: DB model extension (RunContext + platform + data + EXECUTION_MODE)
   ↓
Layer 2: AnalysisContext → RunContext unification (data migration, API swap)
   ↓
Layer 3: Event schema evolution (WRU / WRSC / ARU structured context objects)
   ↓
Layer 4: ExecutionPolicy model introduction (new, no migration risk)
```

Each layer is independently deployable. Layers 1–2 are pure Django concerns. Layer 3 is a cross-service contract change. Layer 4 is additive and has no dependencies on Layers 1–3 beyond the RunContext usecase enum.

---

## Component Boundaries

| Component | Responsibility | Affected by This Milestone |
|-----------|---------------|---------------------------|
| `workflow_manager/models/run_context.py` | RunContext model definition | YES — add `platform`, `data`, extend `RunContextUseCase` |
| `workflow_manager/models/analysis_context.py` | AnalysisContext (to be retired) | YES — deleted after data migration |
| `workflow_manager/models/analysis.py` | Analysis M2M to contexts | YES — `contexts` FK must point to `RunContext` after migration |
| `workflow_manager/models/execution_policy.py` | New: operational constraints | YES — new file |
| `workflow_manager_proc/domain/event/wru.py` | WRU Pydantic model (code-gen) | YES — `computeEnv`/`storageEnv`/`executionMode` become objects |
| `workflow_manager_proc/domain/event/wrsc.py` | WRSC Pydantic model (code-gen) | YES — same fields, same change |
| `workflow_manager_proc/domain/event/aru.py` | ARU Pydantic model (code-gen) | YES — add structured context fields |
| `workflow_manager_proc/domain/event/arsc.py` | ARSC Pydantic model (code-gen) | YES — add structured context fields |
| `workflow_manager_proc/services/workflow_run.py` | WRU processing, context wiring | YES — parse structured objects, update `get_wrsc_hash()` |
| `workflow_manager_proc/services/analysis_run.py` | ARU processing, context wiring | YES — parse structured objects |
| `workflow_manager/serializers/` | REST API surface | YES — `analysis_context.py` deleted; `run_context.py` extended |
| `workflow_manager/viewsets/` | REST API surface | YES — `analysis_context.py` deleted; API route `/analysiscontext` removed or redirected |
| `workflow_manager/urls/base.py` | Route registration | YES — deregister `analysiscontext`, adjust `analysis` update path |

---

## Layer 1: RunContext Model Extension

### What Changes

Add two fields to `RunContext`:
- `platform`: `TextChoices` enum (`ICAV2`, `SEQERA`, `AWS_BATCH`, `AWS_ECS`) — `null=True, blank=True` initially (existing records have no platform)
- `data`: `JSONField` with `default=dict, blank=True` — stores platform-specific properties

Extend `RunContextUseCase` `TextChoices` to add `EXECUTION_MODE`.

### Migration Safety

`platform` and `data` must be nullable/have defaults when first added. Existing `RunContext` records contain compound opaque strings in `name` (e.g. `"icav2-prod-projectX"`). They must not be broken. The new fields are optional enrichment on top of the existing `(name, usecase)` unique key — existing lookup paths (`get_or_create(name=..., usecase=...)`) continue to work unchanged.

```
Migration 0022: AddField RunContext.platform (nullable TextChoices)
Migration 0022: AddField RunContext.data (JSONField, default=dict)
Migration 0022: AlterField RunContextUseCase (add EXECUTION_MODE choice)
```

One migration file. No data migration needed at this step — existing records are valid with nulls.

### Unique Constraint Evolution

The existing `unique_together = ["name", "usecase"]` remains in force. The new `platform` field is not part of the constraint. This is deliberate: the migration from bare-string `computeEnv` names to structured objects will create new `RunContext` records with matching `name` but enriched `platform`/`data`. To avoid constraint collisions, the constraint must evolve to `unique_together = ["name", "usecase", "platform"]` (treating `None` as "legacy") OR name semantics must change so structured contexts have different names (e.g. use platform-qualified names). The recommended approach is to treat `(name, usecase)` as the natural key for legacy records and allow new records created from structured events to use a platform-qualified or UUID-generated key. This decision must be made explicitly before Layer 3 is built — it governs how `establish_workflow_run_contexts()` does its `get_or_create` lookup.

**Recommended:** Change the unique constraint to `["name", "usecase", "platform"]` so that a `RunContext` with `name="icav2-prod-projectX"`, `usecase=COMPUTE`, `platform=None` (legacy) coexists with `name="projectX"`, `usecase=COMPUTE`, `platform=ICAV2` (structured) without conflict.

---

## Layer 2: AnalysisContext → RunContext Unification

### The Problem

`AnalysisContext` is structurally identical to `RunContext` but lives in a separate table (`workflow_manager_analysiscontext`) with its own prefix (`anx`). It has these live connections:
- `Analysis.contexts` (M2M to `AnalysisContext`)
- REST API: `GET/PATCH /api/v1/analysiscontext/`
- Serializers: `AnalysisContextSerializer`, `UpdatableAnalysisContextSerializer`
- `AnalysisContextViewSet`

`AnalysisRun.contexts` already points to `RunContext` (M2M added in migration 0014). `AnalysisContext` is only connected to `Analysis`, not `AnalysisRun`.

### Migration Sequence

**Step 1 — Add M2M from Analysis to RunContext (additive, non-breaking).**
Add `Analysis.run_contexts = ManyToManyField(RunContext)` alongside the existing `Analysis.contexts` M2M to `AnalysisContext`. Do NOT remove `Analysis.contexts` yet.

```
Migration 0023: AddField Analysis.run_contexts (ManyToManyField to RunContext)
```

**Step 2 — Data migration: copy AnalysisContext records into RunContext.**
Write a data migration that:
1. For each `AnalysisContext` record, look up or create a matching `RunContext` by `(name, usecase)`.
2. For each `Analysis`, copy its `analysis.contexts` (AnalysisContext) into `analysis.run_contexts` (RunContext) by mapping through the name+usecase lookup.

```python
# In data migration 0024
def migrate_analysis_contexts(apps, schema_editor):
    AnalysisContext = apps.get_model("workflow_manager", "AnalysisContext")
    RunContext = apps.get_model("workflow_manager", "RunContext")
    Analysis = apps.get_model("workflow_manager", "Analysis")

    for ac in AnalysisContext.objects.all():
        rc, _ = RunContext.objects.get_or_create(
            name=ac.name,
            usecase=ac.usecase,
            defaults={"description": ac.description, "status": ac.status}
        )
        # Link Analysis records that use this AnalysisContext to the RunContext
        for analysis in ac.analysis_set.all():
            analysis.run_contexts.add(rc)
```

**Step 3 — Rename `run_contexts` to `contexts` on Analysis (swap the FK).**
Once data migration is verified:
1. Remove `Analysis.contexts` (old M2M to `AnalysisContext`).
2. Rename `Analysis.run_contexts` to `Analysis.contexts` (M2M to `RunContext`).
3. Update serializers, viewsets: replace `AnalysisContext` imports with `RunContext`.
4. Remove `AnalysisContextViewSet` and its URL route, or keep it as a deprecated redirect returning 410 Gone.
5. Delete `analysis_context.py` model file, serializer, viewset.

```
Migration 0025: RemoveField Analysis.contexts (old M2M to AnalysisContext)
Migration 0025: RenameField Analysis.run_contexts → contexts
Migration 0026: DeleteModel AnalysisContext (after confirming no FK references remain)
```

### API Surface Continuity

The REST endpoint `GET /api/v1/analysiscontext/` serves the same data as `GET /api/v1/runcontext/?usecase=COMPUTE` or STORAGE. After unification, downstream API consumers must migrate to `/runcontext/`. This is a breaking API change. Options:

- **Preferred:** Keep `/analysiscontext/` registered but backed by `RunContext` data filtered for usecases that were previously `AnalysisContext` records. This is a thin compatibility shim requiring no consumer changes.
- **Alternative:** Remove the route and bump the API version to signal the break.

Given the service's internal usage pattern (no known external analysis-context-only consumers), removing the route with a clear deprecation notice is acceptable if coordinated with any OrcaBus consumers.

### `UpdatableAnalysisSerializer` Impact

`UpdatableAnalysisSerializer` currently accepts `contexts` as a list of `AnalysisContext` orcabusIds. After migration, this field must accept `RunContext` orcabusIds. The field's `help_text` currently says "List of AnalysisContext orcabusId" — update it to "List of RunContext orcabusId". The `anx.` prefix in any stored IDs changes to `rnx.` — this affects any callers that store orcabusIds and re-submit them.

---

## Layer 3: Event Schema Evolution

### Current State

All four event Pydantic models (`wru.py`, `wrsc.py`, `aru.py`, `arsc.py`) have `computeEnv: Optional[str]` and `storageEnv: Optional[str]`. These are bare strings. The service code in `establish_workflow_run_contexts()` and `establish_workflow_run_contexts()` does `RunContext.objects.get_or_create(name=event.computeEnv, usecase=...)`.

### Target State

`computeEnv`, `storageEnv`, and `executionMode` become structured objects:
```json
{
  "name": "icav2-prod",
  "platform": "ICAV2",
  "data": { "projectId": "abc123" }
}
```

### Code-Generation Constraint

The Pydantic models are generated from JSON Schema files via `datamodel-code-generator`. The JSON Schema files are the source of truth. To change the event schema:
1. Update the JSON Schema files (`.schema.json`).
2. Re-run `datamodel-code-generator` to regenerate the Pydantic models.
3. Update service code that reads the changed fields.
4. Update `get_wrsc_hash()` and `get_arsc_hash()` to include platform and a canonical hash of `data` (using existing `rfc8785` dependency — already available).

The JSON Schema files are not visible in the provided codebase exploration but are referenced as the upstream source. They must be located and updated as part of this layer.

### Cut-Over Strategy

This is a cross-service contract change. The upstream scheduler (the external event producer) must deploy its schema changes and the workflow manager's schema changes atomically or via a coordinated window.

**Recommended cut-over: coordinated deployment, no feature flag.**

Rationale:
- The `computeEnv`/`storageEnv` fields are `Optional[str]` today. Making them `Optional[ContextObject]` where `ContextObject` itself has all-optional fields allows both old (string) and new (object) producers to coexist — but only if the Pydantic model validates both. This is not straightforward in Pydantic v2 without a Union type.
- The cleaner approach is to define the new schema as `Optional[ContextObject]` where `ContextObject` has `name: str`, `platform: Optional[str]`, `data: Optional[dict]`. Old producers sending a bare string will fail Pydantic validation. The Lambda will fail and EventBridge will retry.
- The PROJECT.md explicitly states "Backward-compatible event processing for old bare-string computeEnv/storageEnv is out of scope — external scheduler is responsible for migrating." This removes the need for a dual-schema compatibility mode.

**Deployment sequence:**
1. Deploy workflow manager with new Pydantic schema (accepts structured objects only).
2. Schedule a brief maintenance window or coordinate with scheduler team.
3. Deploy scheduler with new event emission format.
4. Verify end-to-end with a test WRU event.

If zero-downtime is required, use the Union approach in Pydantic:
```python
computeEnv: Optional[Union[str, ContextObject]] = None
```
and normalise at the service layer — but this is extra complexity for a constraint that's explicitly out of scope.

### Hash Update for WRSC/ARSC Deduplication

`get_wrsc_hash()` currently appends `out_wrsc.computeEnv` (a string) to the keywords list. After schema change, `computeEnv` is an object. The hash must include `platform` and a canonical hash of `data` using `rfc8785` (already a project dependency). Recommended hash contribution:

```python
if out_wrsc.computeEnv:
    keywords.append(out_wrsc.computeEnv.name)
    if out_wrsc.computeEnv.platform:
        keywords.append(out_wrsc.computeEnv.platform)
    if out_wrsc.computeEnv.data:
        keywords.append(canonicalize(out_wrsc.computeEnv.data).hex())
```

This is the same pattern used for Payload deduplication (`hash_payload_data` using `rfc8785`).

### `executionMode` as a New Context Field

WRU and ARU gain an `executionMode` field (structured context object). The service must wire this into `RunContext` with `usecase=EXECUTION_MODE`. The `establish_workflow_run_contexts()` function gains a third block alongside `computeEnv` and `storageEnv`. The WRSC/ARSC mapping functions must emit `executionMode` in the outbound event.

---

## Layer 4: ExecutionPolicy Model

### Placement

`ExecutionPolicy` is a new top-level model in `app/workflow_manager/models/execution_policy.py`. It belongs to `workflow_manager` (not `workflow_manager_proc`) because it is persistent data, not processing logic.

### What It Is Not

`ExecutionPolicy` is explicitly NOT a `RunContext`. It represents operational constraints (approval gates, workflow eligibility) that are orthogonal to the execution environment. It must not inherit or extend `RunContext`. It must not share the `RunContextUseCase` enum.

### Recommended Initial Shape

```python
class ExecutionPolicy(OrcaBusBaseModel):
    orcabus_id = OrcaBusIdField(primary_key=True, prefix='exp')
    name = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    requires_approval = models.BooleanField(default=False)
    eligible_workflows = models.ManyToManyField(Workflow, blank=True)
    status = models.CharField(max_length=255, choices=ExecutionPolicyStatus, default=ExecutionPolicyStatus.ACTIVE)
```

The `AnalysisRun` model gains an optional `execution_policy = models.ForeignKey(ExecutionPolicy, null=True, blank=True, on_delete=models.SET_NULL)`.

### Where in the Service

`ExecutionPolicy` is consulted during ARU READY processing — before `_create_workflow_runs_for_analysis_run()` is called, the policy attached to the `AnalysisRun` is evaluated. If approval is required and not yet granted, the transition to READY is blocked or the WorkflowRun auto-generation is deferred.

This logic belongs in `analysis_run_utils.py` or a new `execution_policy.py` service module, not inline in `_finalise_analysis_run()`.

### API Surface

Add:
- `GET /api/v1/executionpolicy/` — list
- `GET /api/v1/executionpolicy/{id}/` — detail
- `PATCH /api/v1/executionpolicy/{id}/` — update (description, status)

Follow the existing `PatchOnlyViewSet` pattern. No POST endpoint needed initially — policies are created via admin or data fixtures, not by API consumers.

---

## Data Flow After Migration

**WRU processing (post-schema change):**
```
EventBridge → handle_wru_event
  → parse WorkflowRunUpdate (structured computeEnv/storageEnv/executionMode)
  → establish_workflow_run_contexts():
      computeEnv:    RunContext.get_or_create(name, usecase=COMPUTE, platform, data)
      storageEnv:    RunContext.get_or_create(name, usecase=STORAGE, platform, data)
      executionMode: RunContext.get_or_create(name, usecase=EXECUTION_MODE, platform, data)
  → state machine transition
  → map to WRSC (include structured context in hash, emit structured fields)
  → emit WRSC to EventBridge
```

**ARU processing (post-schema change):**
```
EventBridge → handle_aru_event
  → parse AnalysisRunUpdate (structured computeEnv/storageEnv/executionMode)
  → same RunContext wiring as WRU
  → (READY only) check ExecutionPolicy before WorkflowRun auto-creation
  → emit ARSC
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Removing AnalysisContext Before Data Migration Completes
**What goes wrong:** Deleting `AnalysisContext` model before all `Analysis.contexts` FKs are migrated to `RunContext` causes an integrity error on migration rollout.
**Instead:** Three-step migration (add new FK → data migration → remove old FK → delete model). Never skip the middle step.

### Anti-Pattern 2: Changing the Unique Constraint Without Thinking Through get_or_create Semantics
**What goes wrong:** `get_or_create(name=..., usecase=...)` with a `(name, usecase, platform)` unique constraint can silently create duplicate records if callers don't pass `platform` consistently.
**Instead:** Define a canonical `get_or_create_run_context(name, usecase, platform, data)` helper in `run_context.py` and route all creation through it. This is the single place that enforces constraint-consistent lookups.

### Anti-Pattern 3: Putting executionMode in the Hash as a Plain String
**What goes wrong:** `platform` and `data` in the structured context object carry information that affects run identity. Hashing only `name` loses differentiation between two runs on different platforms with the same context name.
**Instead:** Hash `name + platform + rfc8785(data)` for all three context fields in `get_wrsc_hash()` and `get_arsc_hash()`.

### Anti-Pattern 4: Deploying New Pydantic Schema Before Scheduler Is Ready
**What goes wrong:** Lambda handlers fail on every incoming event from the old-schema scheduler. EventBridge retries accumulate. Runs are not tracked.
**Instead:** Keep schema changes behind a deployment coordination gate. Validate with a synthetic test event in the dev/beta stage before promoting to prod.

### Anti-Pattern 5: Wiring ExecutionPolicy Into RunContext
**What goes wrong:** Mixing environment context with operational policy creates a model that's hard to extend — adding an approval gate requires changing a RunContext record, which has cardinality and lifecycle assumptions tied to execution tracking.
**Instead:** Keep `ExecutionPolicy` as a first-class model with its own FK on `AnalysisRun`. Zero shared code or inheritance with `RunContext`.

---

## Build Order Implications

```
Phase A: RunContext enrichment (model + migration)
  - Migration 0022: add platform, data fields; extend RunContextUseCase
  - No service code changes required yet
  - Deployable independently; all existing event processing continues unchanged
  - Tests: RunContext creation with nulls, with platform set; usecase EXECUTION_MODE valid

Phase B: AnalysisContext unification
  - Migration 0023: Analysis.run_contexts M2M to RunContext (additive)
  - Migration 0024: data migration (AnalysisContext → RunContext + Analysis M2M swap)
  - Migration 0025: rename Analysis.run_contexts → contexts; remove old contexts M2M
  - Migration 0026: DeleteModel AnalysisContext
  - Update serializers, viewsets, URL routes
  - Tests: Analysis API returns RunContext IDs; PATCH Analysis still wires contexts correctly

Phase C: Event schema changes
  - Update JSON Schema files for WRU, WRSC, ARU, ARSC
  - Regenerate Pydantic models via datamodel-code-generator
  - Update establish_workflow_run_contexts() for all three use cases
  - Update map_workflow_run_new_state_to_wrsc() / _map_analysis_run_to_arsc()
  - Update get_wrsc_hash() / get_arsc_hash() to include platform + rfc8785(data)
  - Coordinated deployment with upstream scheduler
  - Tests: end-to-end WRU with structured computeEnv; hash includes platform

Phase D: ExecutionPolicy model
  - New model, migration, viewset, serializer
  - Optional FK on AnalysisRun
  - Policy evaluation hook in _finalise_analysis_run() / analysis_run_utils
  - Tests: policy blocks WorkflowRun auto-creation when requires_approval=True
```

Phase C MUST come after Phase A (RunContext has `platform` and `data` columns) and Phase B (no AnalysisContext confusion in serializer layer). Phase D is independent of Phase C — it can be built in parallel with Phase C or after.

---

## Scalability Considerations

| Concern | Current | Post-Migration |
|---------|---------|---------------|
| RunContext table size | Small (one row per named environment) | Slightly larger (new `executionMode` rows; old AnalysisContext rows merged) |
| Query patterns | `contexts.filter(usecase=..., status=ACTIVE)` | Same; add `platform=` filter when needed |
| Unique constraint | `(name, usecase)` | `(name, usecase, platform)` — still small, indexed naturally |
| Event hash computation | MD5 of sorted keywords | Same; rfc8785 canonicalization of `data` adds negligible cost |
| Migration Lambda duration | Seconds | Phase B data migration: proportional to AnalysisContext row count (expected: small) |

---

## Sources

All findings are HIGH confidence — derived directly from codebase analysis:
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager/models/run_context.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager/models/analysis_context.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager/models/analysis.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager/models/analysis_run.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager_proc/services/workflow_run.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager_proc/services/analysis_run.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager_proc/domain/event/wru.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager_proc/domain/event/wrsc.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager_proc/domain/event/aru.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager_proc/domain/event/arsc.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager/urls/base.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/app/workflow_manager/migrations/0014_runcontext_analysisrun_contexts_workflowrun_contexts.py`
- `/opt/code/projects/OrcaBus/service-workflow-manager/.planning/PROJECT.md`
- `/opt/code/projects/OrcaBus/service-workflow-manager/.planning/codebase/ARCHITECTURE.md`
