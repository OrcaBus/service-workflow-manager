# Project Research Summary

**Project:** service-workflow-manager — RunContext enrichment milestone
**Domain:** Django event-driven microservice — model extension, model unification, EventBridge schema evolution
**Researched:** 2026-03-23
**Confidence:** HIGH

## Executive Summary

This milestone extends the `service-workflow-manager` to replace opaque bare-string execution environment references (`computeEnv`, `storageEnv`) with structured, platform-typed context objects. The work spans four interconnected layers: enriching the `RunContext` Django model with `platform` (enum) and `data` (JSONField) fields; retiring the structurally-duplicate `AnalysisContext` model via a data-preserving migration into `RunContext`; evolving the WRU/WRSC/ARU/ARSC EventBridge event schemas to carry structured context objects instead of bare strings; and introducing a new `ExecutionPolicy` model that is deliberately separate from `RunContext`. The codebase already uses PostgreSQL, Django 5.2, Pydantic v2, and a code-generation pipeline (`datamodel-code-generator` from JSON Schema) — all existing patterns are the right tools for this work; no new dependencies are required.

The recommended build order is strictly layered: DB model changes first (safe to deploy independently with no event-processing changes), then `AnalysisContext` unification (pure Django migration work, no cross-service coordination), then event schema evolution (requires coordinated deployment with the upstream scheduler), then `ExecutionPolicy` model introduction (additive, independent). The most critical architectural decision is that `platform` + `data` on `RunContext` define execution environment identity, while `ExecutionPolicy` defines operational constraints — these two concerns must never be merged into a single model. The unique constraint on `RunContext` must evolve from `(name, usecase)` to `(name, usecase, platform)` in a three-step migration to safely coexist with legacy opaque-name records.

The highest-risk work is the event schema evolution phase. Changing `computeEnv` from `Optional[str]` to `Optional[ContextObject]` in the Pydantic models is a breaking contract change with the external scheduler. The service must deploy a permissive schema (accepting both forms or structured only) before the upstream scheduler migrates. Equally risky is the `AnalysisContext` → `RunContext` data migration: Django will not automatically copy M2M through-table rows, and if the model is deleted before the `RunPython` data migration runs, all historical context associations are silently destroyed. Both risks have clear, well-defined mitigations documented in the research.

## Key Findings

### Recommended Stack

The existing stack is the correct stack. No new packages are required. The work uses `django.db.models.JSONField` (built-in since Django 3.1) for heterogeneous platform-specific data, `TextChoices` enums for the `platform` field (consistent with the existing `ExecutionEngine` pattern), `datamodel-code-generator` against JSON Schema draft-04 files to regenerate Pydantic v2 models, and the existing `rfc8785` dependency for canonical JSON hashing of the new `data` field in WRSC/ARSC deduplication. The `OrcaBusBaseModel.save()` → `full_clean()` pipeline enforces model invariants automatically, making Pattern B (Django `clean()` method for per-platform key validation) the correct enforcement point for JSONField content.

**Core technologies:**
- `django.db.models.JSONField`: stores heterogeneous platform-specific data on `RunContext` — PostgreSQL JSONField is the correct tool for opaque-but-queryable blobs that vary by platform
- `models.TextChoices` (`RunContextPlatform`, `RunContextUseCase`): typed, queryable platform and use-case enums — consistent with existing `ExecutionEngine` pattern; prevents string drift
- `datamodel-code-generator` + JSON Schema draft-04: source of truth for event contracts — do not hand-edit generated Pydantic files; update JSON Schema and re-run codegen
- `rfc8785` (already a dependency): canonical JSON serialization for hashing `ContextObject.data` in WRSC/ARSC deduplication hash — reuses existing `hash_payload_data()` pattern

See `.planning/research/STACK.md` for field definition patterns, migration code, and Pydantic v2 codegen strategy.

### Expected Features

The milestone is well-scoped in PROJECT.md. Features fall cleanly into three buckets: must-have (the entire milestone is table stakes), explicitly deferred (ExecutionPolicy), and anti-features to avoid building.

**Must have (table stakes):**
- `platform` field (TextChoices) on `RunContext` — enables filtering by platform, currently impossible without parsing opaque name strings
- `data` JSONField on `RunContext` — ICA needs `projectId`, Seqera needs `workspaceId`, AWS Batch needs `jobQueue`; no single typed-column schema can express all three
- `EXECUTION_MODE` use case on `RunContextUseCase` — scheduler's manual/automated decision must be trackable per run, not inferred
- Structured context objects in WRU/WRSC/ARU/ARSC schemas — `{ name, platform, data }` replaces bare `computeEnv: string`
- WRSC/ARSC hash functions updated to include `platform + rfc8785(data)` — existing raw-string hash inputs are no longer correct
- `AnalysisContext` retired, unified into `RunContext` — two identical models compound maintenance cost; `AnalysisRun.contexts` already points to `RunContext`

**Should have (operational value, low complexity):**
- B-tree index on `RunContext.platform` — supports filter queries once platform traffic grows
- REST API filter on `RunContext.platform` — straightforward DRF FilterSet extension, high operational value
- Documented per-platform `data` JSON schemas (ICAV2, SEQERA, AWS_BATCH) — not a code feature, but essential for scheduler team coordination

**Defer (separate milestone per PROJECT.md):**
- `ExecutionPolicy` model (approval gates, workflow eligibility) — explicitly out of scope for this milestone; entangling it with RunContext enrichment blocks delivery
- Multiple COMPUTE/STORAGE contexts per run — out of scope; current one-per-usecase cardinality is an explicit constraint
- Backward-compatible dual-parsing of old bare-string `computeEnv` — external scheduler owns this migration; building it inside the service creates permanent tech debt

See `.planning/research/FEATURES.md` for platform-specific `data` shapes and event schema patterns.

### Architecture Approach

The architecture is a strictly layered build where each layer is independently deployable and has a safe rollback point. Layer 1 (DB model extension) adds `platform` and `data` to `RunContext` with no service code changes — existing event processing is unaffected. Layer 2 (AnalysisContext unification) is a pure Django migration sequence with no cross-service coordination. Layer 3 (event schema evolution) is the only cross-service concern requiring deployment coordination with the external scheduler. Layer 4 (ExecutionPolicy) is additive and independent of Layers 1-3 beyond the `RunContextUseCase` enum.

**Major components and what changes:**
1. `workflow_manager/models/run_context.py` — gains `platform` (TextChoices) and `data` (JSONField); `RunContextUseCase` gains `EXECUTION_MODE`
2. `workflow_manager/models/analysis_context.py` + `analysis.py` — `AnalysisContext` model is retired via a 4-migration sequence; `Analysis.contexts` re-pointed to `RunContext`
3. `workflow_manager_proc/domain/event/` (wru, wrsc, aru, arsc) — all four Pydantic models regenerated after JSON Schema updates; `computeEnv`/`storageEnv`/`executionMode` become `Optional[ContextObject]`
4. `workflow_manager_proc/services/workflow_run.py` + `analysis_run.py` — `establish_workflow_run_contexts()` updated to parse structured objects; `get_wrsc_hash()` / `get_arsc_hash()` updated to hash `platform + rfc8785(data)`
5. `workflow_manager/models/execution_policy.py` — new first-class model, own table, own FK on `AnalysisRun`; zero shared code or inheritance with `RunContext`

See `.planning/research/ARCHITECTURE.md` for migration sequences, data flow diagrams, and anti-patterns.

### Critical Pitfalls

1. **JSONField `null=True` vs `blank=True` ambiguity corrupts hash inputs** — use `null=True, blank=True, default=None` and treat `None` as the canonical "no platform data" sentinel; enforce `data={} → data=None` normalisation in `RunContext.clean()`. Two `RunContext` records with logically identical data but different `null`/`{}` representations will produce different RFC8785 hash bytes, breaking WRSC deduplication.

2. **`AnalysisContext` M2M data destroyed if table dropped before transfer** — Django auto-generates migrations that drop tables without copying through-table rows first. Write an explicit `RunPython` data migration that iterates `AnalysisContext` records, calls `RunContext.objects.get_or_create(name, usecase)`, and re-inserts the M2M through-table rows before any `RemoveField` or `DeleteModel` operation. Add a row-count assertion in the migration.

3. **EventBridge schema cut-over window breaks Lambda handlers** — changing `computeEnv` from `Optional[str]` to `Optional[ContextObject]` is a breaking Pydantic validation change. Deploy the permissive consumer (this service) before the upstream scheduler deploys the structured producer. The optional+coordinated deployment sequence is: (1) this service accepts new schema, (2) upstream scheduler sends new schema, (3) verify end-to-end.

4. **WRSC/ARSC hash changes break downstream deduplication** — the WRSC `id` is computed over `computeEnv` and `storageEnv` as raw strings; changing their type changes the hash for every future event. Bump `WRSC_SCHEMA_VERSION` when hash inputs change, and add a regression test asserting a known-fixture hash value is stable before and after migration.

5. **`unique_together` constraint + nullable `platform` creates silent duplicates** — Django treats NULL as distinct in `unique_together`, so two rows with `NULL` platform, same name, same usecase can coexist and both pass constraint checks. Migrate in three steps: add nullable `platform` → backfill `platform` on existing rows → tighten constraint to `(name, usecase, platform)`. Gate step 3 behind its own migration that cannot run until backfill is verified.

## Implications for Roadmap

Based on combined research, four phases are recommended. Phases A and B are pure Django concerns with no cross-service risk. Phase C is the only phase that requires external coordination. Phase D is additive and can run concurrently with Phase C.

### Phase A: RunContext Model Enrichment

**Rationale:** The DB model is the foundation for every other change. Adding `platform` and `data` fields with safe nullable defaults is zero-risk and independently deployable. No service code changes, no event schema changes, no cross-service coordination.
**Delivers:** `RunContext` with `platform` (TextChoices), `data` (JSONField), `EXECUTION_MODE` use case. A single Django migration (0022). Existing event processing is unchanged.
**Addresses:** All table-stakes model features; lays groundwork for unique constraint evolution (three-step process beginning here).
**Avoids:** Pitfall 1 (null/blank ambiguity) — define sentinel in `clean()` at model creation time, not later.
**Research flag:** Standard Django patterns — no phase-level research needed.

### Phase B: AnalysisContext Unification

**Rationale:** `AnalysisContext` is structurally identical to `RunContext` and all `AnalysisRun.contexts` references already point to `RunContext` (since migration 0014). Retiring it now, while the model is clean and before event schema changes add complexity, is the safest window. Must come before Phase C because Phase C's serializer updates should target a single context model.
**Delivers:** `AnalysisContext` table retired. `Analysis.contexts` M2M points to `RunContext`. REST API `/analysiscontext/` removed or aliased. Migrations 0023–0026.
**Addresses:** AnalysisContext retirement feature; `anx.` → `rnx.` prefix change documented for API consumers.
**Avoids:** Pitfall 3 (M2M data loss) — explicit `RunPython` migration with row-count assertion; Pitfall 10 (`anx.` ID breakage) — audit API consumers before migration.
**Research flag:** Standard Django data migration pattern — well-documented. Audit of `Analysis.contexts` serializer surface needed before writing migration 0025 (verify `UpdatableAnalysisSerializer` field name and camelCase transform).

### Phase C: Event Schema Evolution

**Rationale:** This is the only cross-service contract change. It depends on Phase A (RunContext has `platform` and `data` columns to receive structured objects) and Phase B (single context model simplifies serializer layer). Requires explicit deployment coordination with the external scheduler team.
**Delivers:** JSON Schema files updated for WRU, WRSC, ARU, ARSC. Pydantic models regenerated. `establish_workflow_run_contexts()` parses structured `ContextObject`. `get_wrsc_hash()` / `get_arsc_hash()` include `platform + rfc8785(data)`. `executionMode` wired as third context field.
**Addresses:** All event schema features; hash function updates; `executionMode` routing.
**Avoids:** Pitfall 4 (deployment window Lambda failures) — deploy this service first, scheduler second; Pitfall 5 (hash deduplication break) — bump `WRSC_SCHEMA_VERSION`, add regression test; Pitfall 7 (`get_or_create` with JSONField) — use `name`+`usecase`+`platform` as identity, `data` in `defaults`; Pitfall 9 (stale generated models) — add CI diff check.
**Research flag:** Needs careful planning. The `establish_workflow_run_contexts()` update must address the `get_or_create` semantics decision (identity = name+usecase+platform; data in defaults). The unique constraint step 3 (tighten to include `platform`) lands here or at end of Phase A — decide explicitly. Verify `datamodel-code-generator` invocation flags against the existing Makefile target before updating JSON Schema files.

### Phase D: ExecutionPolicy Model

**Rationale:** Additive, no risk to existing functionality. Can be developed in parallel with Phase C or after. The only dependency is that `RunContextUseCase.EXECUTION_MODE` exists (Phase A), but `ExecutionPolicy` itself does not depend on RunContext. Must be kept strictly separate from RunContext — the boundary must be enforced at model creation time.
**Delivers:** `ExecutionPolicy` model with own table, prefix `exp`, FK on `AnalysisRun`. Policy evaluation hook in `_finalise_analysis_run()`. REST endpoints `GET/PATCH /api/v1/executionpolicy/`.
**Addresses:** ExecutionPolicy deferred-to-this-phase feature.
**Avoids:** Pitfall 6 (policy data bleeding into RunContext via extra UseCase values) — `ExecutionPolicy` is a first-class model with zero shared code with `RunContext`; Pitfall 11 (`EXECUTION_MODE` name collision with policy concerns) — validate `EXECUTION_MODE` context names against an explicit allowlist (`manual`, `automated`) in service layer.
**Research flag:** Standard Django model + DRF viewset pattern — well-documented. The policy evaluation hook placement (`analysis_run_utils.py` or new `execution_policy.py` service module) should be decided during phase planning.

### Phase Ordering Rationale

- Phase A before B: `AnalysisContext` unification data migration needs to know the final `RunContext` schema (with `platform` and `data`) so migrated records can be created with correct field values rather than requiring a second backfill pass.
- Phase B before C: Event schema serializers should target a single context model. Having `AnalysisContext` still live during Phase C adds serializer confusion and risks the wrong model being updated.
- Phase C after A+B: `establish_workflow_run_contexts()` writes `platform` and `data` to `RunContext` — those columns must exist. The serializer layer must be clean (B complete).
- Phase D parallel or after C: No hard dependency. Can be timebox-scoped independently.

### Research Flags

Phases needing deeper research during planning:
- **Phase C:** `datamodel-code-generator` invocation — verify existing Makefile target flags and JSON Schema draft version before updating schemas; unique constraint step 3 timing decision; `get_or_create` vs `update_or_create` semantics for structured context fields.
- **Phase B:** Pre-migration audit of `AnalysisContext` REST API consumers required — identify all uses of `anx.` IDs before writing migration 0025.

Phases with standard well-documented patterns (skip research-phase):
- **Phase A:** Standard Django `AddField` / `AlterField` / `TextChoices` extension — no novel patterns.
- **Phase D:** Standard Django model + DRF `PatchOnlyViewSet` pattern — no novel patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All stack findings derived from direct codebase analysis; existing packages are the right tools; no new dependencies needed |
| Features | HIGH | Derived directly from production models, event schemas, services, and PROJECT.md; no inference |
| Architecture | HIGH | All component boundaries and migration sequences verified against live code; migration 0014 confirms AnalysisRun already targets RunContext |
| Pitfalls | HIGH | All pitfalls grounded in direct codebase evidence (hash function line references, model field patterns, migration history); not inferred from general patterns |

**Overall confidence:** HIGH

### Gaps to Address

- **`datamodel-code-generator` Makefile invocation flags:** MEDIUM confidence. The codegen approach is correct, but the specific flags and target name in the project's Makefile need verification before updating JSON Schema files. Verify against the existing Makefile before Phase C begins.
- **`Analysis.contexts` serializer surface pre-migration:** `UpdatableAnalysisSerializer` field name and camelCase transform behavior need direct confirmation before writing migration 0025. The field is documented in the architecture research but not confirmed against the live serializer file.
- **`AnalysisContext` REST API consumers:** The research identifies `GET/PATCH /api/v1/analysiscontext/` as a live endpoint with `anx.` prefix IDs. Whether any external OrcaBus consumers hold `anx.` IDs and use them programmatically has not been confirmed. Audit required before Phase B migration.
- **Unique constraint timing:** The three-step migration (add nullable → backfill → tighten constraint) needs a decision on whether the backfill step should populate `platform` for existing opaque-name `RunContext` rows, or leave them as `platform=NULL` (legacy). This decision governs the final unique constraint form and the `get_or_create` lookup strategy in `establish_workflow_run_contexts()`.

## Sources

### Primary (HIGH confidence — direct codebase analysis)
- `/app/workflow_manager/models/run_context.py` — current RunContext model, fields, unique constraint
- `/app/workflow_manager/models/analysis_context.py` — duplicate model to retire
- `/app/workflow_manager/models/analysis.py` — Analysis M2M to AnalysisContext
- `/app/workflow_manager/models/analysis_run.py` — AnalysisRun M2M to RunContext (confirmed in migration 0014)
- `/app/workflow_manager/migrations/0014_runcontext_analysisrun_contexts_workflowrun_contexts.py` — confirms AnalysisRun already targets RunContext
- `/app/workflow_manager_proc/services/workflow_run.py` — `establish_workflow_run_contexts()`, `get_wrsc_hash()`
- `/app/workflow_manager_proc/services/analysis_run.py` — ARU context wiring, `get_arsc_hash()`
- `/app/workflow_manager_proc/domain/event/wru.py`, `wrsc.py`, `aru.py`, `arsc.py` — current Pydantic event models
- `/docs/events/WorkflowRunUpdate/WorkflowRunUpdate.schema.json` + examples — WRU JSON Schema and real event shapes
- `.planning/PROJECT.md` — requirements, out-of-scope declarations, key decisions

### Secondary (MEDIUM confidence — training knowledge, not live docs)
- Django 5.2 JSONField documentation — `JSONField`, key transforms, GIN index support
- Pydantic v2 `BaseModel`, `Optional`, `model_validator` — stable v2 API
- `datamodel-code-generator` flag behavior — verify Makefile invocation before Phase C

---
*Research completed: 2026-03-23*
*Ready for roadmap: yes*
