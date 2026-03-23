---
phase: 01-runcontext-model-enrichment
plan: 01
subsystem: django-model
tags: [django, model, migration, postgresql, test]
dependency-graph:
  requires: []
  provides:
    - RunContextPlatform enum in app/workflow_manager/models/run_context.py
    - platform CharField on RunContext model
    - data JSONField on RunContext model
    - EXECUTION_MODE usecase value
    - UniqueConstraint(nulls_distinct=False) on name+usecase+platform
    - RunContextMinSerializer with platform field
    - Migration 0022 chaining from 0021
  affects:
    - app/workflow_manager/models/run_context.py
    - app/workflow_manager/serializers/run_context.py
    - app/workflow_manager/migrations/
tech-stack:
  added: []
  patterns:
    - UniqueConstraint with nulls_distinct=False (Django 5.2 PostgreSQL-only)
    - DjangoJSONEncoder for JSONField
    - ValidationError raised from clean() for EXECUTION_MODE+platform constraint
key-files:
  created:
    - app/workflow_manager/migrations/0022_runcontext_platform_data_execution_mode.py
    - (RunContextEnrichmentTests class added to) app/workflow_manager/tests/test_models.py
  modified:
    - app/workflow_manager/models/run_context.py
    - app/workflow_manager/serializers/run_context.py
decisions:
  - Django 5.2 full_clean() validates UniqueConstraint(nulls_distinct=False) at the ORM layer before DB, so duplicate-NULL test catches ValidationError not IntegrityError
metrics:
  duration_seconds: 315
  completed_date: "2026-03-23T07:19:09Z"
  tasks_completed: 2
  files_modified: 4
---

# Phase 01 Plan 01: RunContext Model Enrichment Summary

**One-liner:** RunContext model enriched with ICAV2/SEQERA/AWS_BATCH/AWS_ECS platform enum, nullable data JSONField, EXECUTION_MODE usecase, and UniqueConstraint(nulls_distinct=False) replacing unique_together.

## What Was Built

Task 1 updated `app/workflow_manager/models/run_context.py` with:

- `RunContextPlatform` TextChoices enum (ICAV2, SEQERA, AWS_BATCH, AWS_ECS)
- `EXECUTION_MODE` added to `RunContextUseCase`
- `platform` nullable CharField with `choices=RunContextPlatform`
- `data` nullable JSONField with `encoder=DjangoJSONEncoder` and `default=None`
- `clean()` override: normalises `data={}` to `None`, raises `ValidationError` if EXECUTION_MODE+platform is non-NULL
- `UniqueConstraint(fields=["name","usecase","platform"], nulls_distinct=False, name="unique_runcontext_name_usecase_platform")` replacing `unique_together`
- Updated `__str__` to include platform

Task 1 also updated `app/workflow_manager/serializers/run_context.py`:
- `RunContextMinSerializer.Meta.fields` extended with `"platform"`
- `UpdatableRunContextSerializer` left unchanged (platform and data are identity-level, not updatable)

Task 1 generated migration `0022_runcontext_platform_data_execution_mode.py`:
- Chains from `0021_comment_analysis_run_alter_comment_workflow_run`
- Operations: AlterUniqueTogether(set()), AddField(data), AddField(platform), AlterField(usecase), AddConstraint(UniqueConstraint nulls_distinct=False)
- Single atomic migration per D-02

Task 2 added `RunContextEnrichmentTests` class to `app/workflow_manager/tests/test_models.py` with 11 tests covering all 5 requirements (RCM-01 through RCM-05) plus D-04.

## Tests

All 11 new tests pass. All 25 tests in test_models.py pass.

```
Ran 25 tests in 0.419s
OK
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_unique_constraint_nulls_not_distinct caught ValidationError not IntegrityError**

- **Found during:** Task 2 test run
- **Issue:** The plan notes that `full_clean()` "will NOT catch duplicate NULL values at the Django validation layer". In Django 5.2 this is incorrect — `validate_unique()` in `full_clean()` DOES enforce `UniqueConstraint(nulls_distinct=False)` and raises `ValidationError` before the DB-level `IntegrityError` fires.
- **Fix:** Changed `assertRaises(IntegrityError)` to `assertRaises((IntegrityError, ValidationError))` with an updated docstring explaining the Django 5.2 behaviour.
- **Files modified:** `app/workflow_manager/tests/test_models.py`
- **Commit:** f117306

## Known Stubs

None. All fields are wired to the database with a real migration.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| `assertRaises((IntegrityError, ValidationError))` for NULL-distinct test | Django 5.2 `validate_unique()` enforces UniqueConstraint at full_clean() level; test must accept either exception type to remain correct across Django versions |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 (model + serializer + migration) | 35079e3 | feat(01-01): enrich RunContext model with platform, data, EXECUTION_MODE |
| Task 2 (tests) | f117306 | test(01-01): add RunContextEnrichmentTests covering RCM-01 through RCM-05 |

## Self-Check: PASSED

Files verified to exist:
- app/workflow_manager/models/run_context.py: FOUND
- app/workflow_manager/serializers/run_context.py: FOUND
- app/workflow_manager/migrations/0022_runcontext_platform_data_execution_mode.py: FOUND
- app/workflow_manager/tests/test_models.py: FOUND

Commits verified:
- 35079e3: FOUND
- f117306: FOUND
