# Domain Pitfalls

**Domain:** Django model migration + EventBridge schema evolution (RunContext enrichment, AnalysisContext unification)
**Researched:** 2026-03-23
**Confidence:** HIGH — derived directly from codebase inspection and well-established Django/EventBridge patterns

---

## Critical Pitfalls

Mistakes that cause data loss, silent failures, or production outages.

---

### Pitfall 1: JSONField `null=True` vs `blank=True` Confusion Corrupts Constraint Logic

**What goes wrong:**
`JSONField(null=True)` stores SQL NULL for missing values. `JSONField(blank=True)` allows an empty dict `{}` via form validation but still stores `{}` in the DB. If both are set, `None` (Python) and `{}` (empty dict) become two distinct representations of "no data." `OrcaBusBaseModel.save()` calls `full_clean()` on every save — any validator or unique constraint that treats `{}` and `NULL` differently will behave inconsistently across code paths.

**Why it happens:**
The `data` JSONField on `RunContext` will be added to an existing table that has zero nullable JSON columns today. Developers default to `null=True, blank=True` for "optional" fields without thinking through what "absent" means for hashing and equality checks. The WRSC hash function (`get_wrsc_hash`) currently includes `computeEnv` and `storageEnv` as raw strings; once these become structured objects, `{}` vs `None` for `data` would produce different hash bytes for semantically identical contexts.

**Consequences:**
- Two `RunContext` records that are semantically identical produce different hash inputs → duplicate records or broken deduplication
- The state hash (`StateUtil.create_state_hash`) and WRSC event hash (lines 368–384 of `workflow_run.py`) would drift if `data` is inconsistently serialised
- RFC8785 canonical JSON treats `null` and absent key differently — a `data: null` field canonicalises differently than omitting `data` entirely

**Warning signs:**
- `RunContext.objects.get_or_create(name=..., usecase=..., data=...)` raises `MultipleObjectsReturned`
- WRSC event hash collisions or unexpected duplicate state rejections in test
- `full_clean()` raising `ValidationError` on `JSONField` with `{}` value in test teardown

**Prevention:**
- Use `JSONField(null=True, blank=True, default=None)` and treat `None` as the canonical "no platform data" sentinel — never `{}`
- Add a `clean()` method on `RunContext` that normalises `data={}` to `data=None` before save
- When including `data` in any hash, use RFC8785 canonical serialisation and define the canonical form of absent data explicitly (e.g., always serialize `{}` for None before hashing, or skip the field entirely when None)

**Phase:** Addresses the `platform` + `data` JSONField addition to `RunContext`.

---

### Pitfall 2: `unique_together = ["name", "usecase"]` Breaks When `platform` Is Added

**What goes wrong:**
`RunContext` currently enforces `unique_together = ["name", "usecase"]`. The plan adds `platform` as a third dimension. If the unique constraint is not updated to `["name", "usecase", "platform"]`, two contexts for the same name/usecase on different platforms (e.g., `icav2-prod` as COMPUTE on ICAV2 vs SEQERA) will conflict. Conversely, if the constraint is expanded too early without migrating existing `name` values, existing rows that have opaque compound names (e.g., `icav2-prod-projectX`) will have `platform=NULL` and the constraint will pass despite logical duplicates.

**Why it happens:**
The migration adds the `platform` column as `null=True` (required for backward compatibility with existing rows). Django's `unique_together` treats NULL as distinct from every other value in PostgreSQL, so two rows with `NULL` platform, same name, same usecase would violate the constraint — but a row with `NULL` platform and one with `ICAV2` platform would not.

**Consequences:**
- `get_or_create` calls in `establish_workflow_run_contexts()` (lines 192–205 of `workflow_run.py`) silently create duplicate `RunContext` rows when called by the scheduler before data is backfilled
- Existing `RunContext` rows without `platform` become unfindable via new structured lookup paths

**Warning signs:**
- `IntegrityError: duplicate key value violates unique constraint` after migration in staging
- `RunContext.objects.get_or_create(name=..., usecase=..., platform=...)` returning unexpected results when `platform` is `None`

**Prevention:**
- Backfill `platform` on all existing rows before tightening the unique constraint
- Write the migration as three discrete steps: (1) add `platform` nullable, (2) data migration to populate `platform` from existing `name` strings, (3) alter constraint to include `platform` and set `NOT NULL`
- Gate the constraint tightening behind a separate migration that cannot run until the backfill is verified

**Phase:** Addresses `platform` enum field addition to `RunContext`. The three-step migration must be planned as a single ordered migration sequence, not a single `AlterField`.

---

### Pitfall 3: `AnalysisContext` M2M Data Lost if Table Is Dropped Before Transfer

**What goes wrong:**
`AnalysisContext` records are referenced by `Analysis.contexts` (M2M, table `workflow_manager_analysis_analysiscontext`) and indirectly via the `AnalysisContextUseCase` enum. The plan retires `AnalysisContext` and unifies it into `RunContext`. If a migration drops the `AnalysisContext` table (or removes the `Analysis.contexts` M2M field) before copying existing rows into `RunContext` and re-pointing `Analysis.contexts` to `RunContext`, all historical context associations are silently destroyed.

**Why it happens:**
Django's `makemigrations --squash` and auto-generated migration ordering does not know that data inside a table being dropped is live production data. Django will happily generate a migration that does `RemoveField(model_name="analysis", name="contexts")` before `AddField(model_name="analysis", name="contexts", field=ManyToManyField(RunContext))` with no data copy step in between.

**Consequences:**
- Zero M2M rows in `workflow_manager_analysis_runcontext` after migration
- `Analysis` records have no linked contexts; any downstream logic that reads contexts to route workflow runs breaks silently
- Fixtures using `AnalysisContext` (see `sim_analysis.py` approval context FIXMEs) produce no test coverage for this path

**Warning signs:**
- Django-generated migration has `DeleteModel(name="AnalysisContext")` before any `RunDataMigration` step
- `Analysis.objects.prefetch_related("contexts").filter(contexts__isnull=False)` returns empty queryset on staging after migration

**Prevention:**
- Write an explicit `RunPython` data migration step that:
  1. Iterates all `AnalysisContext` rows
  2. Gets or creates a matching `RunContext` with the same `name`, `usecase`, `description`, `status`
  3. Transfers every `Analysis.contexts` M2M through-table row to the new `RunContext` PK
- Only after the `RunPython` step: `RemoveField` the old M2M, then `DeleteModel` the old table
- Confirm row counts before and after in the data migration and raise if counts differ
- The `AnalysisContext` prefix is `anx` and `RunContext` is `rnx` — the PKs differ; the M2M through-table uses the PK as FK, so a simple `UPDATE` won't work; must insert new M2M rows explicitly

**Phase:** Addresses `AnalysisContext → RunContext` unification. This is the highest-risk migration step.

---

### Pitfall 4: EventBridge Schema Change Breaks Downstream Consumers Before Code Is Deployed

**What goes wrong:**
`WRU.computeEnv` changes from `Optional[str]` to a structured context object `{ name, platform, data }`. EventBridge does not version schema validation in rules — rules match on `detail-type` only. Any downstream consumer (Lambda or otherwise) that reads `computeEnv` as a string from WRSC events will receive a dict and fail with a `TypeError` or Pydantic `ValidationError` at the earliest `model_validate` call.

**Why it happens:**
The Pydantic models are code-generated from JSON Schema. When the JSON Schema file is updated and `datamodel-code-generator` is rerun, the new Python class is in the codebase. If the scheduler (upstream producer) deploys the new event schema before this service deploys the new consumer code, or vice versa, there is a window where schema mismatch causes Lambda failures. EventBridge has no built-in schema versioning or consumer negotiation.

**Consequences:**
- Lambda invocation failures during the deployment window
- EventBridge retries the failed event up to the configured retry count; if the retry window outlasts the deployment window, events are replayed successfully — but if the retry window is shorter, events are silently dead-lettered
- The WRSC event emitted by this service still has `computeEnv: str` (the old shape) until this service is also updated — downstream WRSC consumers would then see the old shape, creating a second mismatch moment

**Warning signs:**
- CloudWatch Lambda error alarms fire immediately after upstream scheduler deploys schema change
- Pydantic `ValidationError` in Lambda logs for `WorkflowRunUpdate.computeEnv`
- Dead-letter queue depth rising during deployment window

**Prevention:**
- The new field must be `Optional` in both the WRU inbound schema AND the WRSC outbound schema during the transition period — never make a new structured field required until all producers have migrated
- Deploy a two-phase schema: phase A makes `computeEnv` accept `str | ContextObject` (union), phase B removes the `str` branch after all producers send only objects
- Coordinate deployment order: this service deploys the permissive (union) consumer first, upstream scheduler deploys the structured producer second, then this service deploys the strict consumer last
- Add an explicit EventBridge dead-letter queue to both WRU and ARU Lambda event rules so no events are silently dropped during the window

**Phase:** Addresses WRU/WRSC/ARU event schema evolution. Must be the first implementation phase before any model changes go live.

---

### Pitfall 5: WRSC Event Hash Breaks When `computeEnv`/`storageEnv` Change Shape

**What goes wrong:**
`get_wrsc_hash()` (lines 331–384 of `workflow_run.py`) includes `out_wrsc.computeEnv` and `out_wrsc.storageEnv` as raw strings in the keyword list. Once these fields become structured objects (or their DB representation changes from a plain name string to a structured lookup), the hash input changes — which means the same logical WRSC event produces a different `id` before and after the schema migration. Downstream consumers that store or deduplicate WRSC events by `id` will treat the same event as new.

**Why it happens:**
`get_wrsc_hash` was designed with the current `str` type. The note at line 344 shows that timestamp was intentionally excluded "for now." The function has a known TODO: "allow force creation." If `computeEnv` transitions to an object, the caller must decide what part of that object becomes the hash input — the `name` only, the full canonical JSON, or the `platform` + `name` combination.

**Consequences:**
- WRSC event `id` changes for events that are logically identical → downstream deduplication breaks
- Events that were previously deduplicated are now re-processed by consumers
- State hash (`StateUtil.create_state_hash`) is separate and unaffected, but WRSC event hash drift causes consumer-side idempotency failures

**Warning signs:**
- Downstream consumer tables show duplicate rows for runs that already existed before schema migration
- Integration tests for WRSC hash produce different values after `computeEnv` type change

**Prevention:**
- Before changing the hash function, decide and document the canonical string representation of a context object for hashing purposes (recommendation: `name` field only, matching the current behaviour)
- Add an explicit test asserting that the WRSC `id` for a known fixture is stable across schema versions
- Treat the hash function as a versioned contract — bump `WRSC_SCHEMA_VERSION` (currently `"1.0.0"`) when the hash inputs change, so downstream consumers can detect the break

**Phase:** Must be addressed in the same phase as the WRSC outbound schema change.

---

## Moderate Pitfalls

Mistakes that cause incorrect behavior or require rework, but do not cause data loss.

---

### Pitfall 6: `ExecutionPolicy` Modelled as RunContext UseCase Instead of Separate Model

**What goes wrong:**
`RunContextUseCase` will gain an `EXECUTION_MODE` value. There is a risk of scope creep where operational constraint data (approval gates, workflow eligibility — the `ExecutionPolicy` domain) is also attached as additional `RunContextUseCase` values (e.g., `APPROVAL`, `ELIGIBILITY`). This collapses two orthogonal concerns into a single model.

**Why it happens:**
`AnalysisContextUseCase` already had an `APPROVAL` use case (see `CONCERNS.md` and the commented-out fixture code in `sim_analysis.py` lines 120, 237). The temptation is to carry this forward into `RunContext` by adding more `UseCase` enum values. But approval/eligibility constraints are not execution environment descriptors — they are policy statements that govern whether a run should start, not where it runs.

**Consequences:**
- `ExecutionPolicy` records become entangled with environment context lookups
- `get_or_create` calls for contexts in `establish_workflow_run_contexts()` would inadvertently create policy records on event arrival, bypassing any approval workflow
- Querying "what compute environments exist?" becomes "what contexts of any usecase except policy exist?" — fragile filter logic

**Warning signs:**
- A new `RunContextUseCase.APPROVAL` or `RunContextUseCase.ELIGIBILITY` value is proposed
- Any code that creates `RunContext` records inside `establish_workflow_run_contexts()` handles APPROVAL or ELIGIBILITY cases

**Prevention:**
- `ExecutionPolicy` must be a distinct model with its own table from the start — this is already captured as a Key Decision in `PROJECT.md`
- Keep `RunContextUseCase` strictly to execution environment descriptors: `COMPUTE`, `STORAGE`, `EXECUTION_MODE`
- Document the boundary explicitly: a `RunContext` answers "where does this run execute and how?"; an `ExecutionPolicy` answers "is this run permitted to execute?"

**Phase:** Addresses `ExecutionPolicy` model introduction. The boundary must be enforced at model creation time — it is far harder to separate later.

---

### Pitfall 7: `get_or_create` Context Lookup Fails Silently When `data` Field Is Present

**What goes wrong:**
`establish_workflow_run_contexts()` uses `RunContext.objects.get_or_create(name=..., usecase=...)` to find or create contexts. Once `data` (JSONField) is added to `RunContext`, the same call pattern either (a) ignores `data` in the lookup — meaning two contexts with the same `name`/`usecase` but different `data` resolve to the same record (overwrite semantics) — or (b) includes `data` in the lookup — meaning every event that passes slightly different `data` creates a new record.

**Why it happens:**
`get_or_create` in Django matches on all kwargs passed as the query filter. If `data` is not in the kwargs, it will match any row regardless of `data` content. If `data` is in the kwargs and contains a JSONField, Django compares by exact equality, which is unreliable for deeply nested dicts and inconsistent across PostgreSQL versions.

**Consequences:**
- Duplicate `RunContext` records proliferate in the database
- The `unique_together` constraint triggers `IntegrityError` under concurrent Lambda invocations
- The `unique_together` may not prevent logical duplicates if `platform` is included in the constraint but `data` is not

**Warning signs:**
- `RunContext` table row count grows proportionally to event volume after migration
- `IntegrityError` under load in `establish_workflow_run_contexts()`

**Prevention:**
- Do not include `data` in the `get_or_create` kwargs — treat `name` + `usecase` + `platform` as the identity, and `data` as a property that can be updated on an existing record
- Use `update_or_create(defaults={"data": ...}, name=..., usecase=..., platform=...)` instead of `get_or_create` when the caller also wants to update `data`
- Consider whether `data` should ever update after record creation — if contexts are immutable once created, validate `data` only at creation time

**Phase:** Addresses `data` JSONField addition and the `establish_workflow_run_contexts()` function update.

---

### Pitfall 8: `OrcaBusBaseModel.save()` Calls `refresh_from_db()` — Expensive on JSONField

**What goes wrong:**
`OrcaBusBaseModel.save()` calls `self.refresh_from_db()` after every save to reload custom field annotations. For models without JSONField this is a fast PK lookup. Once `RunContext` carries a JSONField `data`, every `save()` reloads the JSON blob from Postgres. In the atomic transaction path inside `_create_workflow_run()`, a `WorkflowRun` can trigger 2–4 `RunContext` saves (compute + storage + executionMode, each calling `refresh_from_db()`).

**Why it happens:**
`refresh_from_db()` was added to support `OrcaBusIdField` auto-generation, which is set by a Postgres trigger. It is a blanket call, not scoped to fields that need it. `JSONField` data round-trips through Postgres JSON parsing on the reload.

**Consequences:**
- Increased latency per event in the Lambda handler — acceptable at current volume, but latency budget tightens as context objects grow
- If `data` contains large blobs, the reload amplifies I/O

**Warning signs:**
- Lambda duration p99 increases after `RunContext` enrichment is deployed
- DB slow query log shows increased volume of `SELECT * FROM workflow_manager_runcontext WHERE orcabus_id = ...` during event processing

**Prevention:**
- Override `save()` on `RunContext` to call `refresh_from_db(fields=["orcabus_id"])` instead of the full reload, or use `update_fields` on the save call
- This is a latency concern, not a correctness concern — address if measured, not preemptively

**Phase:** Moderate risk during `RunContext` enrichment. Flag for performance testing post-deployment.

---

## Minor Pitfalls

Mistakes that cause confusion or minor rework.

---

### Pitfall 9: Code-Generated Pydantic Models Are Checked In — Regeneration Is a Manual Step

**What goes wrong:**
`wru.py`, `wrsc.py`, `aru.py`, and `arsc.py` are code-generated from JSON Schema files via `datamodel-code-generator`. If the JSON Schema is updated but the regeneration step is skipped or the output is not committed, the Python models diverge from the contract. There is no CI gate that detects schema/model drift.

**Why it happens:**
This is the existing pattern — the timestamp comments at lines 1–3 of each file show they were last generated in August 2025. Schema changes for this milestone require updating the JSON Schema files and re-running the generator.

**Consequences:**
- The Python model silently accepts (and ignores) the new structured `computeEnv` field while the JSON Schema declares it required
- Type-checking with mypy would catch this only if mypy is run against generated types — unlikely to be in CI

**Warning signs:**
- The `timestamp:` comment at the top of the generated file does not match the JSON Schema `$id` or last-modified date
- `computeEnv: Optional[str]` still present in the generated model after schema change

**Prevention:**
- Add a CI check: run `datamodel-codegen` on the schema files and `diff` the output against committed files; fail if there is a diff
- During the milestone, regenerate all four files after every JSON Schema change and commit the result before merging

**Phase:** Must be addressed as part of the event schema evolution phase.

---

### Pitfall 10: `AnalysisContext` Prefix `anx` vs `RunContext` Prefix `rnx` — API Breakage

**What goes wrong:**
`AnalysisContext` records have `orcabus_id` with prefix `anx`. After unification, those same logical contexts will have `rnx` prefixes (or they will be new records). Any external API client that stored `anx.` IDs and uses them to look up contexts via the REST API will receive 404s after the migration.

**Why it happens:**
The `OrcaBusIdField` generates the prefix automatically from the model's declared `prefix` kwarg. There is no registry mapping old IDs to new IDs, and the REST API does not expose redirect semantics.

**Consequences:**
- API clients holding `anx.` IDs cannot retrieve those contexts after migration without an explicit ID mapping

**Warning signs:**
- External tooling (dashboards, CLI scripts) uses `anx.` IDs to filter or retrieve `AnalysisContext` records via the API

**Prevention:**
- Audit all known API consumers of `AnalysisContext` before migrating
- If API compatibility is required: keep the `AnalysisContext` API endpoint as a read-only alias that maps `anx.` IDs to the corresponding `RunContext` record, or document the ID change as a known breaking change with a migration guide
- If the context is purely internal (only the OrcaBus scheduler reads it), a simple deprecation notice is sufficient

**Phase:** Must be assessed before the `AnalysisContext` retirement migration is written.

---

### Pitfall 11: `EXECUTION_MODE` Context Name Collides With Existing Compound Name Convention

**What goes wrong:**
Existing `RunContext` records use opaque compound name strings like `"icav2-prod-projectX"` that implicitly encode platform and project. Adding `EXECUTION_MODE` as a new `UseCase` means a context with `usecase=EXECUTION_MODE` and `name="manual"` or `name="automated"` will be created by `establish_workflow_run_contexts()`. These are low-cardinality, shared records — not run-specific. If the scheduler sends `executionMode` as a compound string with extra data (e.g., `"manual-approval-required"`), the context record becomes a quasi-policy record, violating the boundary with `ExecutionPolicy`.

**Why it happens:**
The current `get_or_create(name=event.computeEnv, usecase=COMPUTE)` pattern treats the name string as opaque. The same pattern applied to `executionMode` will accept any string as a valid mode name with no validation.

**Consequences:**
- `EXECUTION_MODE` contexts accumulate arbitrary string values, defeating the purpose of structured `platform` and `data` fields
- The `ExecutionPolicy` boundary erodes incrementally

**Warning signs:**
- More than 2–3 distinct `EXECUTION_MODE` context names appear in production (`manual`, `automated`, and nothing else should exist)
- `executionMode` event field contains strings with multiple components separated by `-` or `_`

**Prevention:**
- Validate `EXECUTION_MODE` context names against an explicit allowlist (`manual`, `automated`) in the service layer before calling `get_or_create`
- Document that `EXECUTION_MODE` is not extensible in the same way as `COMPUTE` and `STORAGE`

**Phase:** Addresses `EXECUTION_MODE` use case addition to `RunContextUseCase`.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Event schema evolution (WRU/WRSC/ARU `computeEnv` → object) | Producer/consumer deployment window breaks Lambdas (Pitfall 4) | Deploy permissive union schema in this service before upstream scheduler changes |
| WRSC hash function update | Hash breaks downstream deduplication (Pitfall 5) | Bump schema version; add regression test on known fixture hash value |
| `RunContext` `platform` + `data` field addition | `null` vs `{}` ambiguity in JSONField (Pitfall 1) | Define canonical absent-data sentinel; enforce in `clean()` |
| `RunContext` unique constraint update | Constraint breaks or permits duplicates during backfill (Pitfall 2) | Three-step migration: add nullable → backfill → tighten constraint |
| `AnalysisContext` → `RunContext` unification | M2M data lost if drop precedes data copy (Pitfall 3) | Explicit `RunPython` data migration with row-count assertion |
| `establish_workflow_run_contexts()` update for structured fields | `get_or_create` semantics break with JSONField (Pitfall 7) | Use `name`+`usecase`+`platform` as identity keys; `data` in `defaults` |
| `ExecutionPolicy` model introduction | Policy data bleeds into RunContext via extra UseCase values (Pitfall 6) | Hard boundary at model creation; no APPROVAL/ELIGIBILITY UseCase on RunContext |
| Code-generated Pydantic model updates | Stale generated files silently diverge from schema (Pitfall 9) | CI diff check; regenerate on every schema file change |
| `AnalysisContext` REST API retirement | Existing `anx.` ID holders get 404s (Pitfall 10) | Audit consumers; document or alias before retiring endpoint |

---

## Sources

- Codebase inspection: `app/workflow_manager/models/run_context.py`, `app/workflow_manager/models/analysis_context.py`, `app/workflow_manager/models/analysis.py`, `app/workflow_manager/models/workflow_run.py`, `app/workflow_manager/models/analysis_run.py`
- Event models: `app/workflow_manager_proc/domain/event/wru.py`, `wrsc.py`, `aru.py`
- Service layer: `app/workflow_manager_proc/services/workflow_run.py` (hash function, context establishment, state transition)
- Migration history: `app/workflow_manager/migrations/0014_runcontext_analysisrun_contexts_workflowrun_contexts.py`
- Cross-cutting: `.planning/codebase/CONCERNS.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/PROJECT.md`
- Confidence: HIGH for all items — grounded in direct codebase evidence, not inferred from general patterns alone
