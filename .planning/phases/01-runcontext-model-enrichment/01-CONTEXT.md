# Phase 1: RunContext Model Enrichment - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Add `platform` (extensible enum), `data` (JSONField), and `EXECUTION_MODE` use case to the existing `RunContext` model. Deliver safe Django migrations that leave existing records intact and tighten the unique constraint to `(name, usecase, platform)` with NULLS NOT DISTINCT semantics.

No event schema changes, no AnalysisContext work, no new API endpoints — those are Phases 2 and 3.

</domain>

<decisions>
## Implementation Decisions

### Unique Constraint Migration

- **D-01:** The new unique constraint is `(name, usecase, platform)` with **NULLS NOT DISTINCT** — implemented via `Meta.constraints` with `UniqueConstraint(..., nulls_distinct=False)` (Django 4.1+, PostgreSQL 15+ / Aurora PG16 both support this).
- **D-02:** A **single migration file** handles all changes atomically: add `platform` field (nullable), add `data` JSONField, add `EXECUTION_MODE` to usecase choices, drop old `unique_together`, add new `UniqueConstraint` with `nulls_distinct=False`.
- **D-03:** Existing rows are backfilled with `platform=NULL` (they already are NULL — no explicit backfill query needed). NULLS NOT DISTINCT ensures legacy rows still satisfy "one context per name+usecase" because `(name, 'COMPUTE', NULL)` cannot be duplicated.

### EXECUTION_MODE Semantics

- **D-04:** `platform` **must be NULL** for any RunContext with `usecase=EXECUTION_MODE`. This is enforced as a model-level validation rule (in `RunContext.clean()` or equivalent), not just a convention.
- **D-05:** The execution mode value ('manual', 'automated', etc.) is stored in the **`name` field** — consistent with how COMPUTE and STORAGE contexts work today. No special structure needed in `data` for the mode itself.

### Claude's Discretion

- **`platform` and `data` PATCH-ability:** Not discussed — Claude decides whether to include these in `UpdatableRunContextSerializer`. Recommendation: both fields should be **read-only after creation** (not patchable) since `platform` is part of the unique constraint and `data` is platform-specific structured content; changing them post-creation would be semantically odd.
- **`data` field constraints:** Not discussed — Claude decides. Recommendation: accept any valid JSON object (dict); no structural validation at the model level since platform-specific keys vary by design. Default: `null` when omitted.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### RunContext Model
- `app/workflow_manager/models/run_context.py` — Current model definition: fields, `unique_together`, `RunContextUseCase` enum

### Serializers and Viewsets
- `app/workflow_manager/serializers/run_context.py` — All RunContext serializers including `UpdatableRunContextSerializer` (controls PATCH fields)
- `app/workflow_manager/viewsets/run_context.py` — RunContext viewset (PatchOnlyViewSet)

### Migrations
- `app/workflow_manager/migrations/0021_comment_analysis_run_alter_comment_workflow_run.py` — Latest migration (new migration chains from here)

### Requirements
- `.planning/REQUIREMENTS.md` §RunContext Model Enrichment — RCM-01 through RCM-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `OrcaBusBaseModel.clean()` — The base model already calls `full_clean()` before every `save()`. EXECUTION_MODE platform-NULL validation goes in `RunContext.clean()` override, which is called automatically.
- `RunContextSerializer` uses `fields = "__all__"` — `platform` and `data` will appear in GET responses automatically without serializer changes.
- `UpdatableRunContextSerializer` (explicit field list) — must be updated if new fields should be patchable (D-discretion above: likely not).

### Established Patterns
- **Enum as `TextChoices`:** `RunContextUseCase`, `RunContextStatus` both use `models.TextChoices` — `EXECUTION_MODE` follows the same pattern.
- **`unique_together` → `UniqueConstraint`:** This migration pattern changes `Meta.unique_together` to `Meta.constraints`. Django's migration framework generates `RemoveConstraint` + `AddConstraint` operations for this.
- **Nullable fields:** `description` on RunContext is already `blank=True, null=True` — `platform` follows the same nullable pattern.

### Integration Points
- `WorkflowRun` and `AnalysisRun` associate RunContext records via M2M — no changes needed to those associations in Phase 1.
- The `establish_workflow_run_contexts()` service function (Phase 3) will later populate `platform` and `data` from event payloads — Phase 1 only adds the fields; service wiring is out of scope here.

</code_context>

<specifics>
## Specific Ideas

- NULLS NOT DISTINCT constraint is the explicit preference — do not use a sentinel value or leave standard NULL-distinct behavior.
- EXECUTION_MODE validation is a hard model constraint (enforced in `clean()`), not a soft convention.
- Migration is a single file — do not split into two migrations.

</specifics>

<deferred>
## Deferred Ideas

- GIN index on `data` for key-path queries — explicitly deferred to v2 (RCQV2-01 in REQUIREMENTS.md)
- Filter API support for `data__contains` — deferred to v2 (RCQV2-02)
- `platform` + `data` patchability via API — if needed, add to `UpdatableRunContextSerializer` in a future phase

</deferred>

---

*Phase: 01-runcontext-model-enrichment*
*Context gathered: 2026-03-23*
