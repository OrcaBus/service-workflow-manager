---
phase: 01-runcontext-model-enrichment
verified: 2026-03-23T10:45:00Z
status: human_needed
score: 7/7 must-haves verified
re_verification: false
human_verification:
  - test: "Run the full test_models.py suite against a live PostgreSQL instance"
    expected: "All 25 tests pass, including the 11 RunContextEnrichmentTests methods, with no errors or failures"
    why_human: "PostgreSQL is not available in the verification environment. The local settings use PostgreSQL (not SQLite), so automated test execution cannot be completed here. SUMMARY claims 25 tests passed with commit f117306."
  - test: "Apply migration 0022 against a database with existing RunContext rows and verify row count + field values are preserved"
    expected: "Existing rows survive with platform=NULL, data=NULL, original name/usecase/status/description intact; no rows lost"
    why_human: "Cannot connect to a live database to verify the migration's backward-compatibility behaviour on pre-existing data. The migration logic is structurally correct (adds nullable columns, drops old constraint, adds new constraint) but production data safety needs confirmation."
  - test: "Call GET /api/v1/runcontext/ and verify the response includes platform and data fields"
    expected: "Each RunContext object in the API response contains a platform field (null or one of ICAV2/SEQERA/AWS_BATCH/AWS_ECS) and a data field (null or JSON object)"
    why_human: "Cannot start the Django server in this environment. The serializer wiring is verified statically (RunContextSerializer uses fields='__all__'), but live API response format needs confirmation."
---

# Phase 1: RunContext Model Enrichment Verification Report

**Phase Goal:** RunContext records can express execution platform and platform-specific properties as structured, queryable fields
**Verified:** 2026-03-23T10:45:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A RunContext can be created with platform=ICAV2 (or SEQERA/AWS_BATCH/AWS_ECS) and the value persists | ? HUMAN | Model and migration verified; test exists but PG not available to run |
| 2 | A RunContext can carry a data JSONField with arbitrary keys that survive a DB round-trip unchanged | ? HUMAN | Model and migration verified; test exists but PG not available to run |
| 3 | RunContextUseCase includes EXECUTION_MODE and a RunContext with usecase=EXECUTION_MODE can be created | ✓ VERIFIED | `EXECUTION_MODE = "EXECUTION_MODE"` in model; migration AlterField includes it; test method `test_execution_mode_usecase_created` present |
| 4 | Two RunContext records with same name+usecase but different platform values can coexist | ✓ VERIFIED | `UniqueConstraint(fields=["name","usecase","platform"], nulls_distinct=False)` replaces old `unique_together`; test `test_unique_constraint_allows_same_name_usecase_different_platform` present |
| 5 | Existing RunContext records are unaffected; platform backfilled to NULL on legacy rows | ✓ VERIFIED | `platform` is nullable (null=True, blank=True, no default); migration adds field with no NOT NULL constraint; CONTEXT.md D-03 explicitly confirms no RunPython backfill needed |

**Score (static verification):** 5/5 truths structurally VERIFIED

Note: Truths 1 and 2 require a live PostgreSQL connection for full behavioural confirmation. All static indicators (model fields, migration, tests) pass.

### Required Artifacts

| Artifact | Provides | Status | Details |
|----------|----------|--------|---------|
| `app/workflow_manager/models/run_context.py` | RunContextPlatform enum, platform field, data JSONField, EXECUTION_MODE usecase, clean() override, UniqueConstraint(nulls_distinct=False) | ✓ VERIFIED | All 6 elements confirmed present at lines 14-73; `unique_together` absent |
| `app/workflow_manager/serializers/run_context.py` | RunContextMinSerializer with platform in fields list | ✓ VERIFIED | Line 18: `fields = ["orcabus_id", "name", "usecase", "platform"]`; UpdatableRunContextSerializer excludes platform and data |
| `app/workflow_manager/migrations/0022_runcontext_platform_data_execution_mode.py` | Single atomic migration: AlterUniqueTogether(set()), AddField(data), AddField(platform), AlterField(usecase), AddConstraint(nulls_distinct=False) | ✓ VERIFIED | All 5 operations present in correct order; depends on 0021; `nulls_distinct=False` at line 60; no pending migrations detected |
| `app/workflow_manager/tests/test_models.py` | RunContextEnrichmentTests class with 11 test methods covering RCM-01 through RCM-05 | ✓ VERIFIED | Class at line 252; all 11 test methods confirmed present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `run_context.py` | `0022_runcontext_platform_data_execution_mode.py` | Django migration auto-detection | ✓ WIRED | `makemigrations --check --dry-run` exits 0; no pending model changes |
| `run_context.py` | `serializers/run_context.py` | RunContextSerializer fields='__all__' auto-exposes new fields | ✓ WIRED | `RunContextSerializer.Meta.fields = "__all__"` confirmed; `platform` and `data` will appear in all GET responses |
| `serializers/run_context.py` | `viewsets/run_context.py` | RunContextViewSet.serializer_class = RunContextSerializer | ✓ WIRED | Viewset at line 11 uses RunContextSerializer; partial_update switches to UpdatableRunContextSerializer (which correctly excludes platform/data) |

### Data-Flow Trace (Level 4)

Not applicable for this phase. Phase 1 adds model fields and migration only. There is no dynamic data rendering via API that requires a live trace — the serializer auto-exposes new fields via `fields="__all__"`. Platform population from event payloads is deferred to Phase 3 (EVT-06).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| No pending migrations after model changes | `python manage.py makemigrations --check --dry-run workflow_manager` | Exit 0, "No changes detected" | ✓ PASS |
| `unique_together` removed from model | `grep "unique_together" app/workflow_manager/models/run_context.py` | No output | ✓ PASS |
| `nulls_distinct=False` in migration | `grep "nulls_distinct=False" migration 0022` | Found at line 60 | ✓ PASS |
| Migration chains from correct predecessor | `dependencies` in migration 0022 | `("workflow_manager", "0021_comment_analysis_run_alter_comment_workflow_run")` | ✓ PASS |
| Test class has 11 methods | Count of `def test_` in RunContextEnrichmentTests | 11 methods confirmed | ✓ PASS |
| Full test suite | `python manage.py test workflow_manager.tests.test_models.RunContextEnrichmentTests` | PostgreSQL not available — SKIP | ? SKIP (human) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RCM-01 | 01-01-PLAN.md | RunContext exposes platform field (extensible enum: ICAV2, SEQERA, AWS_BATCH, AWS_ECS) | ✓ SATISFIED | `RunContextPlatform` TextChoices enum with all 4 values; nullable CharField on model; migration AddField(platform); 2 tests (test_platform_field_stored_and_returned, test_all_platform_choices_valid) |
| RCM-02 | 01-01-PLAN.md | RunContext exposes data JSONField for platform-specific structured properties | ✓ SATISFIED | `data = models.JSONField(encoder=DjangoJSONEncoder, null=True, blank=True, default=None)`; migration AddField(data); 3 tests (roundtrip, empty-dict-normalisation, null-default) |
| RCM-03 | 01-01-PLAN.md | RunContextUseCase includes EXECUTION_MODE alongside COMPUTE and STORAGE | ✓ SATISFIED | `EXECUTION_MODE = "EXECUTION_MODE"` added to RunContextUseCase; migration AlterField includes it; clean() enforces platform=NULL for EXECUTION_MODE; 2 tests |
| RCM-04 | 01-01-PLAN.md | Unique constraint expanded to (name, usecase, platform) via safe migration | ✓ SATISFIED | UniqueConstraint(fields=["name","usecase","platform"], nulls_distinct=False) replaces unique_together; migration: AlterUniqueTogether(set()) then AddConstraint; platform is nullable so existing rows get platform=NULL with no explicit backfill needed (CONTEXT D-03); 2 tests |
| RCM-05 | 01-01-PLAN.md | platform field is optional (nullable) to accommodate EXECUTION_MODE | ✓ SATISFIED | `platform = models.CharField(..., null=True, blank=True)`; no default forces it non-null; 2 tests (test_platform_nullable, test_legacy_row_unaffected) |

All 5 requirements for Phase 1 are accounted for and satisfied. No orphaned requirements detected.

Requirements outside Phase 1 scope (ACU-01 through ACU-04, EVT-01 through EVT-09, EXP-01 through EXP-04) are correctly assigned to Phases 2, 3, and 4 — not expected here.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| No anti-patterns detected | - | - | - | - |

Checked files:
- `app/workflow_manager/models/run_context.py` — No TODOs, placeholders, or stub returns. `clean()` has real validation logic, not just `pass`. Fields have real DB-backed implementation.
- `app/workflow_manager/serializers/run_context.py` — No stubs. `UpdatableRunContextSerializer.update()` has real logic (empty string guard).
- `app/workflow_manager/migrations/0022_runcontext_platform_data_execution_mode.py` — No stub operations. All 5 operations are substantive.
- `app/workflow_manager/tests/test_models.py` (RunContextEnrichmentTests) — No skipped tests (except the NULLS NOT DISTINCT test which uses `assertRaises((IntegrityError, ValidationError))` — a correct Django 5.2 adaptation, not a stub).

### Notable Design Decisions Verified

1. **NULLS NOT DISTINCT test uses `assertRaises((IntegrityError, ValidationError))`** — This is correct. SUMMARY documents that Django 5.2's `validate_unique()` enforces `UniqueConstraint(nulls_distinct=False)` at the ORM layer, raising `ValidationError` before the DB-level `IntegrityError` fires. The test correctly accepts either exception. This is not a stub — it is a Django version–accurate implementation.

2. **No explicit RunPython backfill in migration** — Correct by design (CONTEXT.md D-03). `platform` is nullable; all existing rows receive `platform=NULL` automatically. The new UniqueConstraint with `nulls_distinct=False` means each pre-existing `(name, usecase)` pair becomes `(name, usecase, NULL)` which is unique by the old constraint, so no duplicates arise. Migration is safe.

3. **`UpdatableRunContextSerializer` excludes platform and data** — Correct per design decision (CONTEXT.md). `platform` is part of the unique constraint; `data` is identity-level. Neither should be patchable post-creation.

### Human Verification Required

#### 1. Full Test Suite Execution

**Test:** Start PostgreSQL (e.g. `docker compose up -d db` from repo root), then run:
`cd app && DJANGO_SETTINGS_MODULE=workflow_manager.settings.local python manage.py test workflow_manager.tests.test_models -v2`

**Expected:** All 25 tests pass (14 pre-existing + 11 new RunContextEnrichmentTests). Output ends with `Ran 25 tests... OK`.

**Why human:** PostgreSQL is not available in the verification environment. The local settings use PostgreSQL (not SQLite) as the only DB backend.

#### 2. Migration Safety on Existing Data

**Test:** Restore a database dump with existing RunContext rows (or seed some manually), then run:
`cd app && DJANGO_SETTINGS_MODULE=workflow_manager.settings.local python manage.py migrate workflow_manager 0022`

**Expected:** Migration applies without error; all pre-existing RunContext rows have `platform=NULL` and `data=NULL`; row count is unchanged; original `name`, `usecase`, `status`, and `description` values are intact.

**Why human:** Cannot connect to a live database with pre-existing data to verify migration backward-compatibility in practice.

#### 3. REST API Field Exposure

**Test:** Start the server and call `GET /api/v1/runcontext/`. Inspect the response body for one RunContext record.

**Expected:** Response includes `platform` (null or one of ICAV2/SEQERA/AWS_BATCH/AWS_ECS) and `data` (null or JSON object) fields at the top level of each RunContext object.

**Why human:** Cannot start the Django server in this environment. The wiring is statically verified (`RunContextSerializer` uses `fields="__all__"`), but live API format needs confirmation.

### Gaps Summary

No gaps found. All 5 requirements (RCM-01 through RCM-05) are satisfied. All 4 artifacts are present and substantive. All key links are wired. No anti-patterns detected. The only items routed to human verification are behavioural (test execution, migration on live data, API response shape) — these cannot be automated without a running PostgreSQL instance.

---

_Verified: 2026-03-23T10:45:00Z_
_Verifier: Claude (gsd-verifier)_
