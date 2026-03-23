# Phase 1: RunContext Model Enrichment - Research

**Researched:** 2026-03-23
**Domain:** Django model extension — TextChoices enum, JSONField, UniqueConstraint with NULLS NOT DISTINCT, model-level clean() validation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** The new unique constraint is `(name, usecase, platform)` with **NULLS NOT DISTINCT** — implemented via `Meta.constraints` with `UniqueConstraint(..., nulls_distinct=False)` (Django 4.1+, PostgreSQL 15+ / Aurora PG16 both support this).
- **D-02:** A **single migration file** handles all changes atomically: add `platform` field (nullable), add `data` JSONField, add `EXECUTION_MODE` to usecase choices, drop old `unique_together`, add new `UniqueConstraint` with `nulls_distinct=False`.
- **D-03:** Existing rows are backfilled with `platform=NULL` (they already are NULL — no explicit backfill query needed). NULLS NOT DISTINCT ensures legacy rows still satisfy "one context per name+usecase" because `(name, 'COMPUTE', NULL)` cannot be duplicated.
- **D-04:** `platform` **must be NULL** for any RunContext with `usecase=EXECUTION_MODE`. This is enforced as a model-level validation rule (in `RunContext.clean()` or equivalent), not just a convention.
- **D-05:** The execution mode value ('manual', 'automated', etc.) is stored in the **`name` field** — consistent with how COMPUTE and STORAGE contexts work today. No special structure needed in `data` for the mode itself.

### Claude's Discretion

- **`platform` and `data` PATCH-ability:** Not discussed — Claude decides whether to include these in `UpdatableRunContextSerializer`. Recommendation: both fields should be **read-only after creation** (not patchable) since `platform` is part of the unique constraint and `data` is platform-specific structured content; changing them post-creation would be semantically odd.
- **`data` field constraints:** Not discussed — Claude decides. Recommendation: accept any valid JSON object (dict); no structural validation at the model level since platform-specific keys vary by design. Default: `null` when omitted.

### Deferred Ideas (OUT OF SCOPE)

- GIN index on `data` for key-path queries — explicitly deferred to v2 (RCQV2-01 in REQUIREMENTS.md)
- Filter API support for `data__contains` — deferred to v2 (RCQV2-02)
- `platform` + `data` patchability via API — if needed, add to `UpdatableRunContextSerializer` in a future phase
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RCM-01 | RunContext model exposes a `platform` field (extensible enum: ICAV2, SEQERA, AWS_BATCH, AWS_ECS) identifying the execution platform | `models.TextChoices` — identical pattern to existing `ExecutionEngine` on `Workflow`; `CharField(max_length=255, choices=RunContextPlatform, null=True, blank=True)` |
| RCM-02 | RunContext model exposes a `data` JSONField for platform-specific structured properties | `models.JSONField(null=True, blank=True, default=None)` using `DjangoJSONEncoder` — same pattern as `Payload.data`; `clean()` normalises `{}` → `None` |
| RCM-03 | RunContextUseCase enum includes `EXECUTION_MODE` alongside existing COMPUTE and STORAGE values | Extend existing `RunContextUseCase(models.TextChoices)` with `EXECUTION_MODE = "EXECUTION_MODE"` |
| RCM-04 | RunContext unique constraint expanded from `(name, usecase)` to `(name, usecase, platform)` via safe migration | Replace `Meta.unique_together` with `Meta.constraints = [UniqueConstraint(fields=["name","usecase","platform"], nulls_distinct=False, name="unique_runcontext_name_usecase_platform")]`; single migration drops old constraint and adds new one |
| RCM-05 | `platform` field is optional (nullable) to accommodate use cases where platform is not applicable | `null=True, blank=True` on the `platform` CharField; NULLS NOT DISTINCT constraint handles NULL parity |
</phase_requirements>

---

## Summary

Phase 1 is a pure Django model extension with no event schema changes and no cross-service coordination. The work adds two fields (`platform` as a new `RunContextPlatform` TextChoices enum, `data` as a JSONField) and one new enum value (`EXECUTION_MODE`) to the existing `RunContext` model, then replaces the `unique_together` constraint with a `UniqueConstraint` that uses `nulls_distinct=False` semantics (PostgreSQL `NULLS NOT DISTINCT`). A single migration file (0022) performs all changes atomically.

The codebase already provides all the patterns needed. `Payload.data` shows the JSONField pattern with `DjangoJSONEncoder`. `Comment.clean()` shows the model-level validation pattern for cross-field constraints. `Workflow.ExecutionEngine` shows the `TextChoices` enum pattern for platform-type fields. Migration 0017 shows the `AlterUniqueTogether` migration pattern; Phase 1 goes further by using the newer `AddConstraint`/`RemoveConstraint` operations to achieve `nulls_distinct=False`, which `AlterUniqueTogether` cannot express.

The only non-trivial decision Claude must make is the `data` field null-vs-blank canonical form: the correct answer (as documented in the prior project research and CONTEXT.md) is `null=True, blank=True, default=None` with a `clean()` normalisation that converts `{}` to `None`, so that "no data" has exactly one representation across all code paths.

**Primary recommendation:** Implement in four code changes — `run_context.py` model (add enum, fields, constraints, clean), `run_context.py` serializers (update `RunContextMinSerializer` fields list), migration 0022 (all DB changes atomically), and `test_models.py` (new `RunContextEnrichmentTests` class covering all five requirements).

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `django.db.models.JSONField` | Built-in (Django 5.2) | Stores platform-specific `data` as PostgreSQL `jsonb` | Already used by `Payload.data` in this codebase; no new dependency |
| `django.db.models.TextChoices` | Built-in | `RunContextPlatform` enum definition | Existing pattern for `ExecutionEngine`, `RunContextUseCase`, `RunContextStatus` |
| `django.db.models.UniqueConstraint` | Built-in (Django 4.1+ for `nulls_distinct`) | Replace `unique_together` with NULLS NOT DISTINCT semantics | `unique_together` cannot express `NULLS NOT DISTINCT`; `UniqueConstraint` can |
| `django.core.exceptions.ValidationError` | Built-in | Raise from `RunContext.clean()` for EXECUTION_MODE platform constraint | Project-wide convention; used in `Comment.clean()` |
| `django.core.serializers.json.DjangoJSONEncoder` | Built-in | JSON encoder for the `data` JSONField | Used on `Payload.data`; handles datetimes and other Django types |

### Supporting

No new packages required. All functionality comes from Django 5.2 built-ins already present in the project.

**Version verification:** All packages are Django built-ins at version 5.2.12 (confirmed in `app/deps/requirements.txt`). No external registry check needed.

---

## Architecture Patterns

### Model Structure After Phase 1

```python
# app/workflow_manager/models/run_context.py

class RunContextPlatform(models.TextChoices):       # NEW
    ICAV2 = "ICAV2"
    SEQERA = "SEQERA"
    AWS_BATCH = "AWS_BATCH"
    AWS_ECS = "AWS_ECS"

class RunContextUseCase(models.TextChoices):
    COMPUTE = "COMPUTE"
    STORAGE = "STORAGE"
    EXECUTION_MODE = "EXECUTION_MODE"               # NEW

class RunContext(OrcaBusBaseModel):
    class Meta:
        constraints = [                             # REPLACES unique_together
            models.UniqueConstraint(
                fields=["name", "usecase", "platform"],
                nulls_distinct=False,
                name="unique_runcontext_name_usecase_platform",
            )
        ]

    # Existing fields unchanged
    orcabus_id = OrcaBusIdField(primary_key=True, prefix='rnx')
    name = models.CharField(max_length=255)
    usecase = models.CharField(max_length=255, choices=RunContextUseCase)
    description = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=255, choices=RunContextStatus, default=RunContextStatus.ACTIVE)

    # New fields
    platform = models.CharField(                    # NEW
        max_length=255, choices=RunContextPlatform,
        null=True, blank=True
    )
    data = models.JSONField(                        # NEW
        encoder=DjangoJSONEncoder,
        null=True, blank=True, default=None
    )

    def clean(self):                                # NEW
        super().clean()
        # Normalise empty dict to None so "no data" has exactly one representation
        if self.data == {}:
            self.data = None
        # EXECUTION_MODE contexts must not specify a platform
        if self.usecase == RunContextUseCase.EXECUTION_MODE and self.platform is not None:
            raise ValidationError(
                {"platform": "platform must be NULL for EXECUTION_MODE contexts."}
            )
```

### Pattern 1: TextChoices Enum (Platform)

**What:** `RunContextPlatform(models.TextChoices)` follows the exact pattern of `ExecutionEngine` on `Workflow`.
**When to use:** Any time a model field has a bounded, queryable set of string values.
**Example:**
```python
# Source: app/workflow_manager/models/workflow.py (existing pattern)
class ExecutionEngine(models.TextChoices):
    UNKNOWN = "Unknown"
    ICA = "ICA"
    SEQERA = "SEQERA"
    AWS_BATCH = "AWS_BATCH"
    AWS_ECS = "AWS_ECS"
    AWS_EKS = "AWS_EKS"
```

### Pattern 2: JSONField with DjangoJSONEncoder

**What:** Store platform-specific structured data as PostgreSQL `jsonb`.
**When to use:** When the data shape varies per row (platform-dependent keys).
**Example:**
```python
# Source: app/workflow_manager/models/payload.py (existing pattern)
data = models.JSONField(encoder=DjangoJSONEncoder)

# Phase 1 variant (nullable, canonical None sentinel):
data = models.JSONField(encoder=DjangoJSONEncoder, null=True, blank=True, default=None)
```

### Pattern 3: model-level clean() for Cross-Field Validation

**What:** Override `clean()` on the model class; called automatically by `OrcaBusBaseModel.save()` via `full_clean()`.
**When to use:** Any cross-field constraint that cannot be expressed as a single-field validator or DB constraint.
**Example:**
```python
# Source: app/workflow_manager/models/comment.py (existing pattern)
def clean(self):
    super().clean()
    has_workflow_run = self.workflow_run_id is not None
    has_analysis_run = self.analysis_run_id is not None
    if has_workflow_run == has_analysis_run:
        raise ValidationError("A comment must be linked to exactly one of ...")
```

Note: `Comment` also calls `self.clean()` explicitly in its own `save()` because `OrcaBusBaseModel.save()` calls `full_clean()` (not `clean()` directly). `full_clean()` calls `clean()` internally, so the override is always invoked. No need for a separate `save()` override on `RunContext` — the base class handles it.

### Pattern 4: UniqueConstraint with nulls_distinct=False

**What:** PostgreSQL `NULLS NOT DISTINCT` unique constraint — two rows with the same `name`, `usecase`, and `platform=NULL` violate the constraint.
**When to use:** When NULL should be treated as a real value for uniqueness purposes (not "distinct from everything").
**Example:**
```python
# Source: Django 4.1+ UniqueConstraint docs
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=["name", "usecase", "platform"],
            nulls_distinct=False,
            name="unique_runcontext_name_usecase_platform",
        )
    ]
```

This replaces `unique_together = ["name", "usecase"]`. Django migration framework generates `RemoveConstraint` (for the old `unique_together`-derived constraint) + `AddConstraint` (for the new `UniqueConstraint`).

### Migration Structure (single file 0022)

```python
# Generated sequence within one migration file
operations = [
    # 1. Add platform field (nullable)
    migrations.AddField(
        model_name="runcontext",
        name="platform",
        field=models.CharField(
            blank=True, max_length=255, null=True,
            choices=[("ICAV2","ICAV2"), ("SEQERA","SEQERA"),
                     ("AWS_BATCH","AWS_BATCH"), ("AWS_ECS","AWS_ECS")],
        ),
    ),
    # 2. Add data JSONField (nullable)
    migrations.AddField(
        model_name="runcontext",
        name="data",
        field=models.JSONField(
            blank=True, default=None, null=True,
            encoder=django.core.serializers.json.DjangoJSONEncoder,
        ),
    ),
    # 3. Update usecase field choices to include EXECUTION_MODE
    migrations.AlterField(
        model_name="runcontext",
        name="usecase",
        field=models.CharField(
            max_length=255,
            choices=[("COMPUTE","COMPUTE"), ("STORAGE","STORAGE"),
                     ("EXECUTION_MODE","EXECUTION_MODE")],
        ),
    ),
    # 4. Remove old unique_together constraint
    migrations.AlterUniqueTogether(
        name="runcontext",
        unique_together=set(),
    ),
    # 5. Add new UniqueConstraint with nulls_distinct=False
    migrations.AddConstraint(
        model_name="runcontext",
        constraint=models.UniqueConstraint(
            fields=["name", "usecase", "platform"],
            name="unique_runcontext_name_usecase_platform",
            nulls_distinct=False,
        ),
    ),
]
```

### Serializer Impact

`RunContextSerializer` uses `fields = "__all__"` — `platform` and `data` appear in GET responses automatically. No changes required to `RunContextSerializer`, `RunContextListParamSerializer`, or `RunContextMinSerializer` for GET responses.

`RunContextMinSerializer` explicitly lists `["orcabus_id", "name", "usecase"]` — `platform` and `data` are intentionally excluded from this minimal view. No changes needed unless the planner decides the min serializer should include `platform`.

`UpdatableRunContextSerializer` lists `["description", "status"]` — per D-discretion, `platform` and `data` are NOT added here (read-only after creation).

### Anti-Patterns to Avoid

- **`unique_together = ["name", "usecase", "platform"]`:** Django treats NULL as distinct in `unique_together`. Two rows with `platform=NULL` same name+usecase would violate this as a DB constraint, but not with NULLS NOT DISTINCT semantics. Use `UniqueConstraint(nulls_distinct=False)` instead.
- **`JSONField(null=True, blank=True)` without `default=None`:** Django field default is `None` if `null=True`, but being explicit avoids ambiguity in form validation and `update_or_create` calls.
- **`JSONField(default=dict)`:** Never use a mutable default. The canonical form for "no data" is `None`, not `{}`.
- **Calling `self.clean()` explicitly in `RunContext.save()`:** Unnecessary — `OrcaBusBaseModel.save()` already calls `full_clean()`, which calls `clean()` internally. Adding a second `save()` override would call `clean()` twice (unlike `Comment.save()` which has its own `save()` for historical reasons).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| NULLS NOT DISTINCT unique constraint | Custom `clean()` checking for duplicate name+usecase+NULL | `UniqueConstraint(nulls_distinct=False)` (Django 4.1+, PostgreSQL 15+) | DB-enforced, concurrent-safe, self-documenting in schema |
| JSON field null normalisation | Multiple code paths that check `if data is None or data == {}` | Single `clean()` normalisation `data={} → data=None` + `default=None` field | Centralised in the model; `full_clean()` always runs before save |
| Enum value validation | `if platform not in ["ICAV2", "SEQERA", ...]` checks scattered in service code | `choices=RunContextPlatform` on the CharField | Django validates choices in `full_clean()` automatically |
| EXECUTION_MODE + platform cross-field constraint | Service-layer `if` checks before each `RunContext.objects.create()` | `RunContext.clean()` override | Enforced at model level regardless of which code path creates the record |

**Key insight:** The `OrcaBusBaseModel.save()` → `full_clean()` pipeline means all model-level constraints (choices validation, `clean()` cross-field checks) run on every save from any code path — service code, management commands, admin, test fixtures. Place constraints in the model, not the service.

---

## Common Pitfalls

### Pitfall 1: JSONField Null vs Empty Dict Corruption

**What goes wrong:** Two RunContext records that are semantically identical (both with "no platform data") can have `data=None` vs `data={}` as distinct DB values. RFC8785 canonical JSON treats these differently, which will corrupt WRSC/ARSC hash inputs in Phase 3.
**Why it happens:** `JSONField(null=True, blank=True)` allows both `None` and `{}` as valid representations of "absent data."
**How to avoid:** `JSONField(null=True, blank=True, default=None)` + `clean()` normalisation: `if self.data == {}: self.data = None`.
**Warning signs:** `RunContext.objects.filter(data={})` returns results in test; hash tests produce different outputs for semantically identical contexts.

### Pitfall 2: unique_together NULL Semantics Trap

**What goes wrong:** Using `unique_together = ["name", "usecase", "platform"]` instead of `UniqueConstraint(nulls_distinct=False)`. PostgreSQL standard `UNIQUE` treats NULL as distinct from every other value — two rows with `platform=NULL`, same name+usecase would VIOLATE this constraint at the DB level (both rows are `(name, usecase, NULL)` and standard unique means they'd conflict... actually they wouldn't because NULL != NULL in standard UNIQUE). Wait — clarification: standard PostgreSQL UNIQUE allows multiple NULLs in the same column. So `unique_together` would allow duplicate `(name, usecase, NULL)` rows. `NULLS NOT DISTINCT` prevents this.
**Why it happens:** Developers assume `unique_together` will enforce "one context per name+usecase when platform is NULL" but standard UNIQUE allows multiple NULLs.
**How to avoid:** Use `UniqueConstraint(fields=["name","usecase","platform"], nulls_distinct=False)` which maps to PostgreSQL `UNIQUE NULLS NOT DISTINCT`.
**Warning signs:** Two RunContext records with same name+usecase+NULL platform can be created without IntegrityError under `unique_together`.

### Pitfall 3: EXECUTION_MODE Platform Constraint Not in clean()

**What goes wrong:** `EXECUTION_MODE` contexts inadvertently get a `platform` value set if the constraint is only documented as a convention rather than enforced in `clean()`.
**Why it happens:** Service code or test fixtures might pass `platform="ICAV2"` with `usecase="EXECUTION_MODE"` without realising it's invalid. Without `clean()`, the record saves successfully.
**How to avoid:** Add `if self.usecase == RunContextUseCase.EXECUTION_MODE and self.platform is not None: raise ValidationError(...)` in `RunContext.clean()`.
**Warning signs:** `RunContext.objects.filter(usecase="EXECUTION_MODE").exclude(platform=None)` returns results.

### Pitfall 4: choices= Constraint Bypassed on EXECUTION_MODE

**What goes wrong:** The `usecase` field has `choices=RunContextUseCase` but existing rows may have been created before `EXECUTION_MODE` was added. Adding the choice value via `AlterField` in the migration changes the Python-level validation but does NOT update existing rows — they remain valid because they use existing COMPUTE/STORAGE values.
**Why it happens:** Django choices are application-level validators, not DB-level `CHECK` constraints. Existing rows are unaffected.
**How to avoid:** This is actually safe — no action needed. Existing COMPUTE/STORAGE rows remain valid after adding EXECUTION_MODE to the choices enum. New rows can now use EXECUTION_MODE.
**Warning signs:** N/A — this is expected behaviour.

### Pitfall 5: RunContextMinSerializer Missing platform in Context Display

**What goes wrong:** `RunContextMinSerializer` only exposes `["orcabus_id", "name", "usecase"]`. After Phase 1, callers reading a "min" serialization of a RunContext (e.g., nested in WorkflowRun API responses) won't see `platform`. This may be intentional (min = identity only) or an oversight.
**Why it happens:** The min serializer was designed before platform existed.
**How to avoid:** Decision point for the planner — either add `platform` to `RunContextMinSerializer.Meta.fields` or accept that platform is only visible in the full `RunContextSerializer` response. Given that `platform` is part of the identity tuple, including it in `RunContextMinSerializer` is recommended.
**Warning signs:** API consumers see a RunContext with `usecase=COMPUTE` but no way to distinguish ICAV2 vs AWS_BATCH contexts in nested responses.

---

## Code Examples

### RunContextPlatform Enum (mirrors ExecutionEngine pattern)

```python
# Source: app/workflow_manager/models/workflow.py (existing pattern to mirror)
class RunContextPlatform(models.TextChoices):
    ICAV2 = "ICAV2"
    SEQERA = "SEQERA"
    AWS_BATCH = "AWS_BATCH"
    AWS_ECS = "AWS_ECS"
```

### RunContext.clean() Override

```python
# Pattern source: app/workflow_manager/models/comment.py
from django.core.exceptions import ValidationError

def clean(self):
    super().clean()
    # Normalise empty dict to canonical None sentinel
    if self.data == {}:
        self.data = None
    # EXECUTION_MODE contexts must not specify a platform (D-04)
    if self.usecase == RunContextUseCase.EXECUTION_MODE and self.platform is not None:
        raise ValidationError(
            {"platform": "platform must be NULL for EXECUTION_MODE contexts."}
        )
```

### Test Pattern for New Fields (mirrors existing WorkflowModelTests)

```python
# Mirrors: app/workflow_manager/tests/test_models.py WorkflowModelTests pattern
class RunContextEnrichmentTests(TestCase):

    def test_platform_field_stored_and_returned(self):
        ctx = RunContext.objects.create(
            name="icav2-prod", usecase=RunContextUseCase.COMPUTE, platform="ICAV2"
        )
        self.assertEqual(ctx.platform, "ICAV2")
        ctx.refresh_from_db()
        self.assertEqual(ctx.platform, "ICAV2")

    def test_data_field_roundtrips(self):
        ctx = RunContext.objects.create(
            name="icav2-prod", usecase=RunContextUseCase.COMPUTE, platform="ICAV2",
            data={"projectId": "proj-abc123"}
        )
        ctx.refresh_from_db()
        self.assertEqual(ctx.data, {"projectId": "proj-abc123"})

    def test_execution_mode_usecase_created(self):
        ctx = RunContext.objects.create(name="manual", usecase=RunContextUseCase.EXECUTION_MODE)
        self.assertEqual(ctx.usecase, "EXECUTION_MODE")
        self.assertIsNone(ctx.platform)

    def test_execution_mode_platform_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            RunContext.objects.create(
                name="manual", usecase=RunContextUseCase.EXECUTION_MODE, platform="ICAV2"
            )

    def test_unique_constraint_allows_same_name_usecase_different_platform(self):
        RunContext.objects.create(name="prod", usecase=RunContextUseCase.COMPUTE, platform="ICAV2")
        RunContext.objects.create(name="prod", usecase=RunContextUseCase.COMPUTE, platform="SEQERA")
        self.assertEqual(2, RunContext.objects.filter(name="prod").count())

    def test_unique_constraint_nulls_not_distinct(self):
        RunContext.objects.create(name="legacy", usecase=RunContextUseCase.COMPUTE, platform=None)
        with self.assertRaises(Exception):  # IntegrityError
            RunContext.objects.create(name="legacy", usecase=RunContextUseCase.COMPUTE, platform=None)

    def test_legacy_rows_unaffected_by_migration(self):
        # Existing rows with platform=None remain valid and accessible
        ctx = RunContext.objects.create(name="old-context", usecase=RunContextUseCase.STORAGE)
        self.assertIsNone(ctx.platform)
        self.assertIsNone(ctx.data)
        self.assertEqual(ctx.status, "ACTIVE")
```

### UpdatableRunContextSerializer (no change needed — platform/data excluded)

```python
# Source: app/workflow_manager/serializers/run_context.py (UNCHANGED)
class UpdatableRunContextSerializer(RunContextBaseSerializer):
    class Meta(OrcabusIdSerializerMetaMixin):
        model = RunContext
        fields = ["description", "status"]  # platform and data NOT added (read-only after creation)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `unique_together` for nullable-column uniqueness | `UniqueConstraint(nulls_distinct=False)` | Django 4.1 (released Dec 2022) | Correctly enforces one row per NULL value; `unique_together` allows multiple NULLs |
| Raw `unique_together` in Meta | `Meta.constraints` list with named constraints | Django 2.2+ (UniqueConstraint introduced) | Named constraints are introspectable, can be deferred, support expressions and conditions |

**Deprecated/outdated:**
- `unique_together`: Still works but cannot express `NULLS NOT DISTINCT`, condition filters, or `deferrable` constraints. Django docs recommend migrating to `Meta.constraints`.

---

## Open Questions

1. **Should `RunContextMinSerializer` include `platform`?**
   - What we know: `RunContextMinSerializer` is used for nested context representation. `platform` is part of the uniqueness identity after Phase 1.
   - What's unclear: Whether nested API consumers (e.g., `WorkflowRunSerializer` context lists) need platform to distinguish ICAV2 vs AWS_BATCH contexts in embedded responses.
   - Recommendation: Add `platform` to `RunContextMinSerializer.Meta.fields`. It is identity-level information, not verbose detail. The planner should confirm or override.

2. **`data` field null vs empty dict normalisation scope**
   - What we know: `clean()` will normalise `{}` → `None`. The `data` field default is `None`.
   - What's unclear: Whether `update_or_create` calls in later phases should also guarantee `None` as the "no data" canonical form, or whether the `clean()` path is sufficient.
   - Recommendation: The `clean()` path is sufficient for Phase 1. Document the sentinel contract (`None` means "no data") in the model docstring for Phase 3.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 1 is a pure Django code/migration change. No external tools, services, or CLIs beyond the existing Python 3.12 / Django 5.2 runtime are required. PostgreSQL 16 with `NULLS NOT DISTINCT` (requires PG 15+) is confirmed available via Aurora PG16 as specified in CLAUDE.md.

---

## Project Constraints (from CLAUDE.md)

The following CLAUDE.md directives are binding on Phase 1 implementation:

| Directive | Impact on Phase 1 |
|-----------|-------------------|
| Python 3.12, Django 5.2, Pydantic v2 | No constraint conflict — all changes use Django 5.2 built-ins |
| `OrcaBusBaseModel.save()` calls `full_clean()` → `clean()` is automatically called | `RunContext.clean()` override will fire on every save; no explicit `save()` override needed on `RunContext` |
| All DB writes in Lambda handlers are `@transaction.atomic` | Migration atomicity guaranteed by Django migration framework; no Lambda writes in Phase 1 |
| `full_clean()` before every save | Model-level `ValidationError` from `clean()` will correctly prevent invalid RunContext saves |
| Model classes in `PascalCase`, files in `snake_case` | New enum `RunContextPlatform` in existing file `run_context.py` |
| Enums extend `models.TextChoices` for Django model field choices | `RunContextPlatform(models.TextChoices)` is the correct pattern |
| Calls `refresh_from_db()` after save | Adds one DB round-trip per RunContext save — acceptable latency impact for Phase 1 volume |
| Backward compatibility: existing `RunContext` records must not break | D-03 (NULL backfill) + NULLS NOT DISTINCT constraint preserves all existing rows |
| `unique_together = ["name", "usecase"]` existing constraint | Must be explicitly removed in migration (`AlterUniqueTogether(unique_together=set())`) before adding the new `UniqueConstraint` |
| Migration path required for schema changes | Single migration 0022 (per D-02) — chains from 0021 |

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `app/workflow_manager/models/run_context.py` — current model definition (fields, `unique_together`, `RunContextUseCase`)
- `app/workflow_manager/models/payload.py` — `JSONField(encoder=DjangoJSONEncoder)` pattern
- `app/workflow_manager/models/comment.py` — `clean()` override pattern with `ValidationError`
- `app/workflow_manager/models/workflow.py` — `ExecutionEngine(models.TextChoices)` pattern
- `app/workflow_manager/models/base.py` — `OrcaBusBaseModel.save()` calling `full_clean()` then `refresh_from_db()`
- `app/workflow_manager/serializers/run_context.py` — all serializer classes, `UpdatableRunContextSerializer` field list
- `app/workflow_manager/viewsets/run_context.py` — `PatchOnlyViewSet` usage
- `app/workflow_manager/tests/test_models.py` — `WorkflowModelTests` pattern for new test class
- `app/workflow_manager/tests/factories.py` — no `RunContextFactory` exists (tests use direct `objects.create()`)
- `app/workflow_manager/migrations/0021_comment_analysis_run_alter_comment_workflow_run.py` — latest migration (0022 chains from this)
- `app/workflow_manager/migrations/0017_alter_workflow_unique_together_workflow_code_version_and_more.py` — `AlterUniqueTogether` migration pattern
- `.planning/phases/01-runcontext-model-enrichment/01-CONTEXT.md` — locked decisions D-01 through D-05
- `.planning/research/PITFALLS.md` — Pitfalls 1 and 2 directly apply to Phase 1

### Secondary (MEDIUM confidence — training knowledge, consistent with codebase patterns)
- Django 5.2 `UniqueConstraint(nulls_distinct=False)` documentation — available since Django 4.1; PostgreSQL 15+ required; Aurora PG16 satisfies this
- Django `JSONField` `null=True, blank=True, default=None` canonical pattern for nullable JSON columns

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are Django 5.2 built-ins already in use
- Architecture patterns: HIGH — all patterns derived from direct codebase inspection of existing models, serializers, migrations
- Pitfalls: HIGH — derived from codebase evidence and prior project research (PITFALLS.md); pitfalls 1 and 2 directly confirmed against live code

**Research date:** 2026-03-23
**Valid until:** 2026-06-23 (stable Django patterns; no time-sensitive ecosystem churn)
