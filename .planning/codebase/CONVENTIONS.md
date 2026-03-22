# Coding Conventions
> Generated: 2026-03-23
> Focus: Naming conventions, code structure, import organization, style patterns across the Python Django/DRF codebase and TypeScript CDK infrastructure layer

## Language Split

This repo has two distinct layers with different conventions:
- **Python (Django/DRF)**: all application logic under `app/`
- **TypeScript (AWS CDK)**: all infrastructure under `infrastructure/`, tests under `test/`

---

## Python Conventions

### File Naming

- Files use `snake_case`: `workflow_run.py`, `analysis_run_state.py`, `event_utils.py`
- Test files are prefixed with `test_`: `test_viewsets.py`, `test_workflow_run.py`
- Fixtures and support files do not use the `test_` prefix: `factories.py`, `case.py`, `sim_workflow.py`
- Event domain models use short abbreviations matching the event schema names: `wru.py` (WorkflowRunUpdate), `wrsc.py` (WorkflowRunStateChange), `aru.py` (AnalysisRunUpdate), `arsc.py` (AnalysisRunStateChange)

### Class Naming

- Model classes: `PascalCase` matching the domain concept — `WorkflowRun`, `AnalysisRunState`, `LibraryAssociation`
- Manager classes always paired with their model and named `<ModelName>Manager`: `WorkflowRunManager`, `StateManager`, `WorkflowManager`
- Viewset classes follow `<Resource>ViewSet`: `WorkflowRunViewSet`, `WorkflowRunActionViewSet`
- Serializer classes follow `<Resource>Serializer` or `<Resource><Variant>Serializer`: `WorkflowRunSerializer`, `WorkflowRunDetailSerializer`, `WorkflowRunListParamSerializer`
- Test case classes follow `<Subject>Tests` or `<Subject>TestCase`: `WorkflowRunSrvUnitTests`, `WruEventHandlerUnitTests`, `OrcaBusBaseManagerTestCase`
- Factory classes follow `<Model>Factory`: `WorkflowFactory`, `WorkflowRunFactory`, `StateFactory`

### Function and Variable Naming

- Functions and variables use `snake_case` throughout
- Private/internal functions at module level are prefixed with `_`: `_create_workflow_run()`, `_build_keyword_params()`, `_validate_ordering()`
- Constants use `UPPER_SNAKE_CASE`: `ASSOCIATION_STATUS`, `WRSC_SCHEMA_VERSION`, `RUNNING_MIN_TIME_DELTA_SEC`, `TIMEDELTA_1H`
- Frozen sets of constants use `frozenset`: `CUSTOM_QUERY_PARAMS`, `ALLOWED_ORDER_FIELDS`

### Enum Patterns

- Enums extend `models.TextChoices` for Django model field choices: `ExecutionEngine`, `ValidationState`
- Domain-level enums with aliases extend Python `Enum` directly: `Status` in `app/workflow_manager/models/common.py`
- The `Status` enum carries both a canonical convention string and a list of aliases for normalization:
  ```python
  class Status(Enum):
      DRAFT = "DRAFT", ['DRAFT', 'INITIAL', 'CREATED']
      RUNNING = "RUNNING", ['RUNNING', 'IN_PROGRESS']
  ```
- Use case enums in context models: `RunContextUseCase`, `AnalysisContextUseCase`

### Model Conventions

All models inherit from `OrcaBusBaseModel` (`app/workflow_manager/models/base.py`), which:
- Calls `full_clean()` before every `save()` to enforce validation
- Calls `refresh_from_db()` after save so prefixed `orcabus_id` values are returned correctly

Every model has a paired manager inheriting from `OrcaBusBaseManager`:
```python
class WorkflowRunManager(OrcaBusBaseManager):
    pass

class WorkflowRun(OrcaBusBaseModel):
    objects = WorkflowRunManager()
```

Primary keys are always `OrcaBusIdField` with a model-specific short prefix:
- `wfl` — Workflow
- `wfr` — WorkflowRun
- `stt` — State
- `lib` — Library
- `pld` — Payload
- `fqr` — Readset
- `ana` — Analysis
- `anx` — AnalysisContext
- `rnx` — RunContext
- `cmt` — Comment
- No prefix — LibraryAssociation

The `OrcaBusIdField` (`app/workflow_manager/fields.py`) stores a bare 26-char ULID internally and annotates with `{prefix}.{ulid}` on read via `from_db_value`. Stripping the prefix is handled by `get_prep_value` which takes the last 26 chars.

Every model implements `__str__` returning a human-readable string with key fields:
```python
def __str__(self):
    return f"ID: {self.orcabus_id}, portal_run_id: {self.portal_run_id}, workflow_run_name: {self.workflow_run_name}"
```

### Viewset Conventions

All read-only viewsets inherit from `BaseViewSet` (`app/workflow_manager/viewsets/base.py`):
```python
class BaseViewSet(ReadOnlyModelViewSet, ABC):
    lookup_field = "orcabus_id"
    lookup_url_kwarg = "orcabus_id"
    lookup_value_regex = "[^/]+"
    ordering = ["-orcabus_id"]
    pagination_class = StandardResultsSetPagination
```

Lookup is always by `orcabus_id`, not Django's default integer pk.

Specialized base classes exist for controlled mutation:
- `PatchOnlyViewSet` — GET, POST, PATCH (no PUT, no DELETE)
- `PostOnlyViewSet` — GET, POST (no update, no DELETE)
- `NoDeleteViewSet` — GET, POST, PUT, PATCH (no DELETE)

### Serializer Conventions

All serializers inherit from `SerializersBase` (`app/workflow_manager/serializers/base.py`), which supports optional camelCase output via `camel_case_data=True` kwarg.

The `OrcabusIdSerializerMetaMixin` marks `orcabus_id` as read-only in serializer `Meta.extra_kwargs` to ensure correct OpenAPI schema generation.

The REST API output is camelCase via `djangorestframework-camel-case` middleware. Internal Django field names remain `snake_case`.

### Pydantic Event Models

Event domain models under `app/workflow_manager_proc/domain/event/` use Pydantic `BaseModel` (generated from JSON schema). Fields follow camelCase matching the event schema:
```python
class WorkflowRunUpdate(BaseModel):
    portalRunId: str
    workflowRunName: str
    analysisRun: Optional[AnalysisRun] = None
```

The `AWSEvent` wrapper uses `Field(..., alias='detail-type')` for the hyphenated EventBridge field.

### Import Organization

1. Standard library (`logging`, `os`, `uuid`, `datetime`, `hashlib`)
2. Third-party (`django.*`, `rest_framework.*`, `pydantic.*`, `factory.*`, `mockito`)
3. Internal — `workflow_manager.*` and `workflow_manager_proc.*`

No barrel/`__init__` re-exports at app level; models are re-exported from `app/workflow_manager/models/__init__.py` for convenience.

### Logging

Every module initializes a logger at module level:
```python
logger = logging.getLogger(__name__)   # preferred in base/model files
logger = logging.getLogger()           # used in service/test files
logger.setLevel(logging.INFO)          # set explicitly in test and service files
```

Log level is set to `INFO` globally in `base.py` settings; tests and services also set it explicitly.

### Error Handling

- Domain exceptions are defined in `app/workflow_manager/errors.py` (`RerunDuplicationError`)
- Django `ValidationError` is the standard for model-level constraint violations
- Pydantic `ValidationError` is used for event schema violations
- Services return `(bool, object)` tuples rather than raising on soft failures (e.g. `update_workflow_run_to_new_state` returns `(success, state)`)
- `FieldError` from bad query params is caught silently and returns `qs.none()`

### API Response Format

Paginated responses follow a consistent envelope:
```json
{
  "links": { "next": "...", "previous": "..." },
  "pagination": { "count": 100, "page": 1, "rows_per_page": 10 },
  "results": [...]
}
```

Query param names: `rows_per_page` (not `page_size`), `page`.

### Transactions

Database writes in service layer use `@transaction.atomic` at the top-level public function:
```python
@transaction.atomic
def create_workflow_run(event: wru.WorkflowRunUpdate):
    ...
```

Inner helper functions (prefixed `_`) are not independently decorated.

---

## TypeScript Conventions

### File Naming

- Test files: `*.test.ts` under `test/`
- Config files: `jest.config.js`, `tsconfig.json`, `eslint.config.mjs`

### Code Style

- Prettier enforces formatting (`pnpm prettier`)
- ESLint enforces linting (`pnpm lint`)
- TypeScript strict compilation verified before test run (`tsc && jest`)

### Test Style

Infrastructure tests use Jest with `describe`/`test` blocks. CDK snapshot tests use `Template.fromStack()` assertions (`aws-cdk-lib/assertions`). Security tests use `cdk-nag` with `AwsSolutionsChecks`.

---

## Comments

Test methods include a comment with the exact `manage.py test` command to run that specific test:
```python
def test_create_workflow_run(self):
    """
    python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_create_workflow_run
    """
```

This is consistent across all test files and serves as runbook documentation.

Inline comments use `#` and are placed above or beside the relevant line. Multi-paragraph explanations use docstrings.

`TODO` and `FIXME` are used actively; `TODO` for future enhancements, `FIXME` for known incorrect behaviour that needs correction.
