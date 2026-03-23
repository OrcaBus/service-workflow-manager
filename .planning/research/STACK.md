# Technology Stack

**Project:** service-workflow-manager — RunContext extension milestone
**Researched:** 2026-03-23
**Confidence:** HIGH for patterns derived from codebase reading; MEDIUM for Django 5.2/Pydantic v2 API specifics (verified against training knowledge, no live doc access)

---

## Scope of This Document

This is a **stack-dimension** research file for the RunContext enrichment milestone. It does not re-document the full service stack (see `.planning/codebase/STACK.md`). It covers:

1. Django `JSONField` patterns for structured metadata with queryability
2. Pydantic v2 schema evolution: structured objects replacing bare strings, backward-compatible optional fields
3. Django migration strategy for `AnalysisContext` → `RunContext` model unification
4. What NOT to use and why, for each area

---

## Existing Stack Baseline (Relevant Subset)

| Technology | Version | Relevant to this milestone |
|------------|---------|---------------------------|
| Django | 5.2.12 | Model field additions, migrations |
| djangorestframework | 3.16.1 | Serializer updates for new fields |
| psycopg | 3.3.2 (psycopg3) | PostgreSQL JSONField storage and querying |
| pydantic | 2.12.5 | Event schema evolution |
| datamodel-code-generator | (dev dep) | Regenerating Pydantic models from updated JSON Schema |
| rfc8785 | 0.1.4 | Canonical JSON hashing — relevant to WRSC `id` hash update |

---

## 1. Django JSONField for Structured Metadata

### Recommendation

Use `django.db.models.JSONField` (built-in since Django 3.1, no additional package required) with PostgreSQL as the backend. The existing codebase already uses PostgreSQL via psycopg3, so all JSON operators are available.

**Why JSONField, not a separate relation:** The `data` field on `RunContext` is meant to hold platform-specific properties that vary by platform (ICAV2 project ID, Seqera workspace ID, AWS Batch queue ARN, etc.). The schema is heterogeneous by design — different keys per platform. A separate related table would require either a discriminated union of FK tables (complex) or an EAV pattern (fragile). JSONField is the correct tool for opaque-but-queryable platform-specific blobs.

### Field Definition Pattern

```python
# In RunContext model
from django.db import models

class RunContext(OrcaBusBaseModel):
    class Meta:
        unique_together = ["name", "usecase"]  # existing — keep

    orcabus_id  = OrcaBusIdField(primary_key=True, prefix='rnx')
    name        = models.CharField(max_length=255)
    usecase     = models.CharField(max_length=255, choices=RunContextUseCase)
    platform    = models.CharField(max_length=64, choices=RunContextPlatform, null=True, blank=True)
    data        = models.JSONField(null=True, blank=True, default=None)

    description = models.CharField(max_length=255, blank=True, null=True)
    status      = models.CharField(max_length=255, choices=RunContextStatus, default=RunContextStatus.ACTIVE)

    objects = RunContextManager()
```

**`null=True, blank=True, default=None` rationale:** Existing `RunContext` records have no platform-specific data. Setting `null=True` avoids a NOT NULL constraint failure on the existing rows when the column is added. `default=None` means the migration ADD COLUMN will set existing rows to NULL cleanly. This is safer than `default={}` which shares a mutable dict reference (Python gotcha) and would write `{}` to all existing rows unnecessarily.

**Do not use `default={}`** — Django's JSONField serializes it fine, but it causes every existing row to be set to `{}` on migration, which is meaningless noise. Use `null=True` with `default=None` to distinguish "no data provided" from "empty data object explicitly set".

### QuerySet Patterns for JSONField

Django 5.2 provides the following lookups for JSONField against PostgreSQL:

**Key presence check:**
```python
# Contexts where 'projectId' key exists in data
RunContext.objects.filter(data__has_key='projectId')
# PostgreSQL: data ? 'projectId'
```

**Key path traversal:**
```python
# Match on nested key
RunContext.objects.filter(data__projectId='my-project')
# PostgreSQL: data->>'projectId' = 'my-project'

RunContext.objects.filter(data__workspace__id=42)
# PostgreSQL: data->'workspace'->>'id' = '42'
```

**isnull for missing data field:**
```python
RunContext.objects.filter(data__isnull=False)
```

**contains lookup (subset matching):**
```python
# Contexts whose data contains at least these keys+values
RunContext.objects.filter(data__contains={'projectId': 'proj-abc'})
# PostgreSQL: data @> '{"projectId": "proj-abc"}'
```

**Confidence:** HIGH — Django JSONField querying with `__has_key`, `__contains`, and key path traversal (`__keyname`) are stable Django ORM features since Django 3.1, well-documented, and unchanged in 5.x.

### GIN Index for Queryability

If `data` fields will be filtered in production queries (e.g., "find all RunContexts for a given ICAV2 project"), add a GIN index in the migration:

```python
# In migration operations list
migrations.AddIndex(
    model_name='runcontext',
    index=models.Index(
        fields=['data'],
        name='runcontext_data_gin_idx',
        # opclasses=['jsonb_path_ops'],  # use for @> queries only
        # omit opclasses for full key traversal flexibility
    ),
)
```

For this codebase's access patterns (filter by `platform` + `usecase`, occasional lookup of `data` keys), a **standard B-tree index on `platform`** is sufficient. The GIN index on `data` is only warranted if you frequently do `data__contains=` or `data__has_key=` queries in hot paths. At current scale, defer the GIN index — it adds write overhead and the query volume through this service is low (Lambda-scale, not OLTP).

**Recommendation:** Add B-tree index on `platform` only. Flag GIN index as a future optimization.

### Validation of JSONField Content

`JSONField` stores anything JSON-serializable — there is no schema enforcement at the DB level. Enforce structure at the application layer using one of two patterns:

**Pattern A — Pydantic validator on the model (recommended for this codebase):**
```python
from pydantic import BaseModel, model_validator
from typing import Optional

class RunContextData(BaseModel):
    """Base schema — platform-specific schemas extend this."""
    pass

class Icav2ContextData(RunContextData):
    projectId: str
    region: Optional[str] = None

class SeqeraContextData(RunContextData):
    workspaceId: int
    workspaceName: Optional[str] = None
```

Use these Pydantic models as validation helpers in the service layer when constructing `RunContext` records from incoming event data. Do not attach them to the Django model's `save()` — that would add Pydantic as a Django model concern and break the clean separation between the ORM layer and the event processing layer.

**Pattern B — Django model `clean()` method:**
```python
def clean(self):
    if self.platform == RunContextPlatform.ICAV2 and self.data:
        required_keys = {'projectId'}
        if not required_keys.issubset(self.data.keys()):
            raise ValidationError(f"ICAV2 context data must contain: {required_keys}")
```

`OrcaBusBaseModel.save()` already calls `full_clean()`, which calls `clean()`. Pattern B is therefore automatically enforced on every save — which is the correct place for invariant enforcement in this ORM. Use Pattern B for per-platform key validation.

**Use both:** Pattern A for deserializing structured data from incoming events in the service layer; Pattern B for DB-level invariant protection.

---

## 2. Pydantic v2 Schema Evolution

### Current State

All four event schemas (`wru.py`, `wrsc.py`, `aru.py`, `arsc.py`) are **code-generated** from JSON Schema files in `docs/events/`. The Pydantic models must not be hand-edited — the source of truth is the `.schema.json` files. Schema evolution requires:

1. Update the JSON Schema file
2. Regenerate the Pydantic model via `datamodel-code-generator`
3. Update the service layer to use the new structured fields

### Schema Evolution Strategy: `Union[str, ContextObject]` vs Separate Field

**What's changing:** `computeEnv: Optional[str]` and `storageEnv: Optional[str]` evolve to structured context objects `{ name, platform, data }`.

**Rejected approach — `Union[str, ContextObject]`:** Using `Union[str, ContextObject]` (a discriminated union accepting both the old string and the new object) would require every consumer to handle both branches. The PROJECT.md explicitly states that backward compat for old bare-string format is OUT OF SCOPE — the external scheduler is responsible for migration. Therefore, do not introduce a `Union` type. Do a clean field type replacement.

**Recommended approach — direct field replacement with Optional:**

In JSON Schema (the source of truth), replace:
```json
"computeEnv": { "type": "string" }
```
with:
```json
"computeEnv": { "$ref": "#/definitions/ContextObject" }
```

And add the definition:
```json
"ContextObject": {
  "type": "object",
  "required": ["name"],
  "properties": {
    "name":     { "type": "string" },
    "platform": { "type": "string" },
    "data":     { "type": "object" }
  }
}
```

Keep `computeEnv`, `storageEnv`, and `executionMode` as `Optional` (not required) at the JSON Schema level — they are optional today and remain optional. `datamodel-code-generator` will emit `Optional[ContextObject] = None`.

This produces clean Pydantic v2 output:
```python
class ContextObject(BaseModel):
    name: str
    platform: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class WorkflowRunUpdate(BaseModel):
    ...
    computeEnv: Optional[ContextObject] = None
    storageEnv: Optional[ContextObject] = None
    executionMode: Optional[ContextObject] = None  # new field
```

**Why this works for backward compatibility:** `computeEnv` is already `Optional[str] = None` in the current schema. Changing its type from `str` to `ContextObject` is a breaking change at the field type level, but the field itself remains optional. Any consumer that was sending `null`/omitting `computeEnv` continues to work. Only consumers actively sending a `computeEnv` string must update. The PROJECT.md constraint confirms this is acceptable — the external scheduler coordinates.

### Pydantic v2 Field Validators

For the WRSC `id` hash update (including `platform` and canonical hash of `data` in the hash inputs), use a `model_validator` on `WorkflowRunStateChange` rather than a field validator. This keeps the hash computation in one place, consistent with the existing `get_wrsc_hash()` function in `workflow_run.py`. The Pydantic model should remain a thin data container — hash computation belongs in the service layer, not in the model.

**Do not add `@field_validator` to the code-generated Pydantic models.** They are regenerated from JSON Schema on every schema change. Any custom validators added to the generated files will be lost. Instead, maintain validation logic in the service layer (`services/workflow_run.py`, `services/analysis_run.py`).

### `datamodel-code-generator` Configuration

The existing toolchain uses `datamodel-code-generator` with the JSON Schema files as input. Key considerations for the new schema:

- JSON Schema draft-04 is currently used (see `"$schema": "http://json-schema.org/draft-04/schema#"` in existing schemas). Stick with draft-04 for consistency — `datamodel-code-generator` handles it reliably.
- The `ContextObject` definition should be added to all three affected schemas (WRU, WRSC, ARU) independently to avoid cross-file references that `datamodel-code-generator` doesn't handle well in single-file generation mode.
- Add `executionMode` to ARU schema aligned with WRU — same `ContextObject` definition, same Optional treatment.

**Confidence:** HIGH for the JSON Schema + codegen approach (this is how the project already works). MEDIUM for specific `datamodel-code-generator` flag behavior (verify against the project's existing codegen invocation in the Makefile or scripts).

### WRSC Hash Update

`get_wrsc_hash()` in `workflow_run.py` currently appends `out_wrsc.computeEnv` (a string) to the hash keywords list. After the schema change, `computeEnv` becomes a `ContextObject`. The hash must be updated to include structured content.

**Recommended pattern for hashing `ContextObject`:**
```python
if out_wrsc.computeEnv:
    keywords.append(out_wrsc.computeEnv.name)
    if out_wrsc.computeEnv.platform:
        keywords.append(out_wrsc.computeEnv.platform)
    if out_wrsc.computeEnv.data:
        # Use existing rfc8785 canonical hash for the data blob
        keywords.append(hash_payload_data(out_wrsc.computeEnv.data))
```

This reuses the existing `hash_payload_data()` from `event_utils.py` (RFC8785 + SHA-256) for the `data` blob, consistent with how `Payload.data` is handled. The `name` and `platform` are simple strings appended directly. This is the cleanest reuse of existing infrastructure.

---

## 3. Migration Strategy: AnalysisContext to RunContext Unification

### Current State

Two structurally identical models exist:
- `RunContext` (`run_context.py`) — table `workflow_manager_runcontext`, prefix `rnx`, linked to `WorkflowRun.contexts` and `AnalysisRun.contexts`
- `AnalysisContext` (`analysis_context.py`) — table `workflow_manager_analysiscontext`, prefix `anx`, linked to `Analysis.contexts` (not `AnalysisRun.contexts`)

Critically: **`AnalysisRun.contexts` already points to `RunContext`**, not `AnalysisContext`. This was done in migration `0014`. The `AnalysisContext` model is still present but its FK relationships have been partially migrated away. The remaining question is what still references `AnalysisContext`.

### What Still References AnalysisContext

From reading the model files and services:
- `Analysis.contexts` is a ManyToMany to `AnalysisContext` (see `analysis.py`)
- `AnalysisContext` is imported in `analysis_context.py` and exposed through `models/__init__.py`
- No service code was found directly creating `AnalysisContext` records — the service layer uses `RunContext` exclusively

**Action required before migration:** Confirm that `Analysis.contexts` FK is the only remaining reference to `AnalysisContext`. Read `analysis.py` and any viewsets/serializers that expose `AnalysisContext`.

### Migration Approach: Data-Preserving Unification

This is a **model unification migration**, not a simple column drop. The steps are:

**Step 1 — Add `RunContext` FK to `Analysis.contexts`**

Add a new ManyToMany field on `Analysis` pointing to `RunContext` (alongside the existing `AnalysisContext` M2M):
```python
# Temporary dual-field state during migration
class Analysis(OrcaBusBaseModel):
    contexts = models.ManyToManyField(AnalysisContext)       # existing — will be removed
    run_contexts = models.ManyToManyField(RunContext)         # new — temporary name
```

Migration operation: `AddField` for `run_contexts`.

**Step 2 — Data migration: copy AnalysisContext records to RunContext**

Write a `RunPython` migration that:
1. Iterates all `AnalysisContext` records
2. For each, calls `RunContext.objects.get_or_create(name=ac.name, usecase=ac.usecase)` — the unique constraint `(name, usecase)` on `RunContext` means identical entries are deduplicated automatically
3. For each `Analysis` that has `AnalysisContext` records, adds the corresponding `RunContext` to `Analysis.run_contexts`

```python
def migrate_analysis_contexts_to_run_contexts(apps, schema_editor):
    AnalysisContext = apps.get_model('workflow_manager', 'AnalysisContext')
    RunContext = apps.get_model('workflow_manager', 'RunContext')
    Analysis = apps.get_model('workflow_manager', 'Analysis')

    for analysis in Analysis.objects.prefetch_related('contexts').all():
        for ac in analysis.contexts.all():
            rc, _ = RunContext.objects.get_or_create(
                name=ac.name,
                usecase=ac.usecase,
                defaults={
                    'description': ac.description,
                    'status': ac.status,
                }
            )
            analysis.run_contexts.add(rc)
```

**Step 3 — Rename `run_contexts` to `contexts` on `Analysis`**

Once data is migrated:
1. `RemoveField` the old `contexts` (AnalysisContext M2M) from `Analysis`
2. `RenameField` `run_contexts` → `contexts` on `Analysis`

Or equivalently: drop the old M2M, rename the new M2M. Use `RenameField` to preserve the through-table name if it matters for the API.

**Step 4 — Remove AnalysisContext model**

```python
migrations.DeleteModel(name='AnalysisContext')
```

This step only works once all FK/M2M references to `AnalysisContext` are gone. Django will enforce this.

**Step 5 — Update `Analysis.contexts` serializer**

Any DRF serializer for `Analysis` that serializes `.contexts` will now resolve to `RunContext` records. Update the serializer to use `RunContextSerializer` (or whatever is appropriate).

### Why NOT "just rename the table"

Renaming `AnalysisContext` to `RunContext` via a SQL `ALTER TABLE RENAME` is not viable because:
1. `RunContext` already exists as a separate table
2. Both have existing data (and the deduplication of identical `(name, usecase)` pairs must be handled explicitly)
3. Django migrations cannot express "merge two tables" as a single operation

### Migration Sequencing and Atomicity

Each step above should be a **separate numbered migration file** (not a single giant migration). This allows:
- Rollback of individual steps if an issue is found in production
- Clear audit trail in git history

Step 2 (data migration with `RunPython`) must use `atomic=True` (the default) so that the data copy is rolled back on failure. Django wraps `RunPython` in the migration's transaction by default.

**Risk flag:** If `AnalysisContext` has a large number of records with `(name, usecase)` values that do NOT exist in `RunContext`, the `get_or_create` in step 2 will create many new `RunContext` records. This is expected and correct. If the values DO overlap (same `(name, usecase)` in both tables), `get_or_create` deduplicates correctly — the existing `RunContext` record is reused.

**Confidence:** HIGH for the overall approach (this is a standard Django model unification pattern). HIGH for the `RunPython` data migration approach. MEDIUM for the exact field state of `Analysis.contexts` — verify by reading `analysis.py` directly before writing migrations.

---

## 4. RunContextUseCase: Adding EXECUTION_MODE

### Current State

```python
class RunContextUseCase(models.TextChoices):
    COMPUTE = "COMPUTE"
    STORAGE = "STORAGE"
```

### Recommendation

Add `EXECUTION_MODE` to the `TextChoices` enum:

```python
class RunContextUseCase(models.TextChoices):
    COMPUTE        = "COMPUTE"
    STORAGE        = "STORAGE"
    EXECUTION_MODE = "EXECUTION_MODE"
```

**Why `TextChoices` not a free string:** `TextChoices` ensures only known values pass `full_clean()` validation (which is called on every `save()` via `OrcaBusBaseModel`). It is self-documenting and enables `RunContext.objects.filter(usecase=RunContextUseCase.EXECUTION_MODE)` queries. Inconsistent casing or typos in event data are caught at the model layer before they reach the DB.

**Migration required:** Adding a new choice to a `TextChoices` field does NOT require a migration if the `choices` parameter is only for validation/display. However, since the field is stored as a `CharField(max_length=255)`, the new choice value `"EXECUTION_MODE"` is within the length constraint. Run `makemigrations` — Django will generate an `AlterField` migration for the choices tuple. This is a display-only migration (no schema change in PostgreSQL), but it is required to keep the migration state consistent.

The `unique_together = ["name", "usecase"]` constraint means each `(name, EXECUTION_MODE)` pair is unique — consistent with how COMPUTE and STORAGE work today.

---

## 5. RunContextPlatform: New TextChoices Field

### Recommendation

Add a `platform` field as a nullable `CharField` with `TextChoices`:

```python
class RunContextPlatform(models.TextChoices):
    ICAV2     = "ICAV2"
    SEQERA    = "SEQERA"
    AWS_BATCH = "AWS_BATCH"
    AWS_ECS   = "AWS_ECS"

class RunContext(OrcaBusBaseModel):
    ...
    platform = models.CharField(
        max_length=64,
        choices=RunContextPlatform,
        null=True,
        blank=True,
    )
```

**Why `null=True`:** Existing `RunContext` records have no platform value. A non-null field with no default would require either a fake default or a multi-step migration. `null=True` allows clean ADD COLUMN without touching existing rows.

**Why not an `IntegerChoices`:** String choices are transparent in the DB, in the API JSON response, and in EventBridge event payloads. The `Workflow.execution_engine` field already uses a string TextChoices pattern — be consistent.

**Migration:** Single `AddField` operation. Django generates this automatically.

**Do not add `platform` to the `unique_together` constraint at this stage.** The existing `(name, usecase)` uniqueness is sufficient and adding `platform` would break `get_or_create(name=..., usecase=...)` calls throughout the service layer. The uniqueness semantics remain `(name, usecase)` — the name already encodes enough identity.

---

## 6. What NOT to Use

| Approach | Why Not |
|----------|---------|
| `HStoreField` for `data` | Limited to flat `{string: string}` maps; no nesting; requires PostgreSQL `hstore` extension. `JSONField` is strictly superior for heterogeneous structured data. |
| `EAV pattern` (separate `key/value` table) | Complex queries, no type safety, no nesting. JSONField is the correct Django-idiomatic choice. |
| Separate `Icav2Context`, `SeqeraContext` tables | Multi-table inheritance adds join complexity. The `data` JSONField with `platform` enum achieves the same typing at lower cost. |
| `Union[str, ContextObject]` in Pydantic event models | Overengineers backward compat that is explicitly out of scope. Makes every consumer branch on type. Use clean field replacement. |
| Adding validators to generated Pydantic model files | Files are regenerated on schema changes. Validators go in the service layer. |
| Single mega-migration for AnalysisContext unification | Hard to debug, hard to roll back. Use sequential numbered migrations. |
| `RunPython(atomic=False)` for data migration | Never disable atomicity unless you have a specific reason (e.g., large dataset with explicit savepoints). At this service's data volume, the default atomic wrapping is correct. |
| GIN index on `data` JSONField at launch | Premature optimization. Lambda invocation volume is low. Add only if query profiling shows slowness on `data__contains=` lookups. |

---

## 7. Serializer and API Considerations

The DRF serializers for `RunContext` and `Analysis` will need updates:

**`RunContextSerializer`:** Add `platform` and `data` fields. `data` is a `JSONField` — DRF serializes it as-is (native Python dict → JSON object). No custom serializer field needed.

**`AnalysisSerializer`:** If `Analysis.contexts` is currently serialized, it will continue to work after unification because the FK target changes but the field name stays the same.

**camelCase transform:** `djangorestframework-camel-case` is in the middleware stack. `platform` stays `platform` (single word). `data` stays `data`. No renaming issues.

**OpenAPI schema (`drf-spectacular`):** The `data` JSONField will be typed as `object` in the OpenAPI spec — this is correct. If you want per-platform schema documentation, add `@extend_schema_field(OpenApiTypes.OBJECT)` with an example on the serializer field. This is a documentation enhancement, not a functional requirement.

---

## Sources

- Codebase reading (HIGH confidence): all model files, migration files, service layer, event schema files in this repository
- Django 5.2 JSONField documentation (MEDIUM confidence — from training knowledge, not live docs): `django.db.models.JSONField`, key transforms, GIN index support
- Pydantic v2 `BaseModel`, `Optional`, `model_validator` (MEDIUM confidence — from training knowledge, Pydantic 2.x stable API)
- `datamodel-code-generator` codegen behavior (MEDIUM confidence — from training knowledge; verify existing Makefile invocation targets)
- Django `RunPython` migration pattern for data migrations (HIGH confidence — well-established, widely documented pattern)
