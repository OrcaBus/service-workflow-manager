<!-- GSD:project-start source:PROJECT.md -->
## Project

**service-workflow-manager**

An event-driven Django microservice within the OrcaBus platform that tracks the lifecycle and state of workflow runs and analysis runs across heterogeneous execution environments (ICA, Seqera, AWS Batch). It receives `WorkflowRunUpdate` and `AnalysisRunUpdate` events from an external scheduler via EventBridge, persists state transitions with deduplication, and emits downstream `WorkflowRunStateChange` / `AnalysisRunStateChange` events. A REST API exposes run history and limited write operations.

**Core Value:** Accurate, deduplicated state tracking of workflow and analysis runs regardless of which execution platform or project space they ran on.

### Constraints

- **Compatibility**: Event schema changes are a cross-service contract — upstream scheduler must be coordinated with
- **Tech stack**: Python 3.12, Django 5.2, Pydantic v2; event models code-generated from JSON Schema
- **Backward compatibility**: Existing `RunContext` records and API consumers must not break; migration path required for `AnalysisContext` → `RunContext` unification
- **Atomicity**: All DB writes in Lambda handlers are `@transaction.atomic`; schema changes must preserve this guarantee
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 — Application logic, Lambda handlers, Django app (`app/`)
- TypeScript 5.9.3 — CDK infrastructure definitions (`infrastructure/`)
- SQL — PostgreSQL migration scripts (`app/workflow_manager/migrations/`, `app/init-db.sql`)
## Runtime
- Python 3.12 (specified in `app/Dockerfile`: `public.ecr.aws/docker/library/python:3.12`)
- AWS Lambda runtime: `aws_lambda.Runtime.PYTHON_3_12` with `Architecture.ARM_64`
- Package manager: pnpm 10.30.2 (declared in `package.json` `packageManager` field)
- Lockfile: `pnpm-lock.yaml` present
## Python Frameworks & Libraries
- Django 5.2.12 — Core web framework (`app/deps/requirements.txt`)
- djangorestframework 3.16.1 — REST API layer
- djangorestframework-camel-case 1.4.2 — JSON camelCase transformation for API I/O
- drf-spectacular 0.29.0 — OpenAPI schema generation
- psycopg[binary] 3.3.2 — PostgreSQL adapter (psycopg3)
- django-iam-dbauth 0.2.1 — AWS IAM authentication for PostgreSQL in production
- serverless-wsgi 3.1.0 — Bridges Django WSGI app to AWS Lambda events (`app/api.py`)
- Werkzeug 3.1.5 — WSGI utilities (used by `runserver_plus`)
- aws-xray-sdk — Distributed tracing (no pinned version; latest used)
- boto3 — AWS SDK (unpinned in test deps; Lambda runtime provides it in production)
- pydantic 2.12.5 — Event schema validation for domain models (`app/workflow_manager_proc/domain/event/`)
- rfc8785 0.1.4 — JSON Canonicalization Scheme for state hashing/deduplication
- ulid-py 1.1.0 — ULID generation for `OrcaBusIdField` (`app/workflow_manager/fields.py`)
- django-cors-headers 4.9.0 — CORS middleware
- django-environ 0.13.0 — Environment variable configuration
- libumccr 0.4.1 — Shared UMCCR utilities (includes `libeb` for EventBridge emission)
- cachetools 6.2.4 — Caching utilities
- six 1.17.0 — EventBridge schema registry compatibility shim
- regex 2025.11.3 — EventBridge schema registry compatibility shim
## Python Test Dependencies
- pytest 9.0.2 — Test runner (alongside Django's built-in test runner via `python manage.py test`)
- factory_boy 3.3.3 — Test data factories
- mockito 1.5.5 — Mock/stub library
- coverage 7.13.1 — Code coverage
- pytz 2025.2 — Timezone utilities
- boto3 — AWS SDK (included for tests)
## Python Dev Dependencies
- django_extensions — Extra management commands (includes `runserver_plus`)
- openapi-spec-validator — Validates generated OpenAPI specs
- datamodel-code-generator — Generates Pydantic models from JSON Schema event files
- black (Python formatter, target py312, invoked via `make lint`)
## CDK / Infrastructure Frameworks
- aws-cdk-lib 2.240.0+ — Core CDK library (`package.json`)
- aws-cdk 2.1107.0+ — CDK CLI (dev dependency)
- @aws-cdk/aws-lambda-python-alpha 2.234.1-alpha.0 — `PythonFunction` and `PythonLayerVersion` constructs
- constructs 10.5.1+ — CDK construct base
- @orcabus/platform-cdk-constructs 1.0.2 — Shared OrcaBus platform constructs (API Gateway, deployment pipeline, shared config)
- cdk-nag 2.37.55 — CDK security/compliance checks
- ts-jest 29.4.6 — TypeScript test runner for Jest
- jest 30.2.0 — JavaScript test runner
- typescript-eslint 8.56.1 — TypeScript linting
- eslint 10.0.2 — JavaScript/TypeScript linter
- prettier 3.8.1 — Code formatter
- ts-node 10.9.2 — TypeScript execution for CDK entrypoint
## Build Tools
- `pnpm cdk synth` — Synthesizes CloudFormation from TypeScript CDK
- Entry point: `bin/deploy.ts` (invoked via `pnpx ts-node`)
- TypeScript compiler options: ES2020 target, CommonJS modules, strict mode enabled (`tsconfig.json`)
- `make install` — Installs Python deps via pip from `deps/requirements-dev.txt`
- `python manage.py migrate` — Applies Django migrations
- Docker: `public.ecr.aws/docker/library/python:3.12` base image
## Configuration
- `DJANGO_SETTINGS_MODULE` — Selects settings module (`workflow_manager.settings.local` / `.it` / `.aws`)
- `EVENT_BUS_NAME` — AWS EventBridge bus name
- `PG_HOST` — PostgreSQL host (production)
- `PG_USER` — PostgreSQL user (production)
- `PG_DB_NAME` — PostgreSQL database name (production)
- `AWS_XRAY_CONTEXT_MISSING` — X-Ray context missing behavior
- `AWS_XRAY_TRACING_NAME` — X-Ray service name
- `DJANGO_SECRET_KEY` — Django secret key
- `DJANGO_DEBUG` — Debug mode flag
- `workflow_manager.settings.local` — Local development (SQLite-style path default)
- `workflow_manager.settings.it` — Integration tests (PostgreSQL, configurable host/port)
- `workflow_manager.settings.aws` — Production AWS (IAM auth PostgreSQL, CORS restricted)
- `tsconfig.json` — TypeScript compiler configuration
- `eslint.config.mjs` — ESLint flat config
- `jest.config.js` — Jest configuration
- `cdk.json` — CDK app entrypoint and context
- `pnpm-workspace.yaml` — pnpm workspace + dependency overrides
## Platform Requirements
- Docker + Docker Compose (PostgreSQL 16 via `public.ecr.aws/docker/library/postgres:16`)
- Python 3.12
- Node.js (compatible with pnpm 10.x)
- pnpm 10.30.2
- AWS CLI (optional, for S3 DB dump downloads)
- AWS Lambda (ARM64, Python 3.12)
- Deployed via AWS CDK pipeline (`OrcaBus-StatelessWorkflowManager`)
- Stages: BETA, GAMMA, PROD
- GitHub repo: `OrcaBus/service-workflow-manager`, branch: `main`
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Language Split
- **Python (Django/DRF)**: all application logic under `app/`
- **TypeScript (AWS CDK)**: all infrastructure under `infrastructure/`, tests under `test/`
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
- Use case enums in context models: `RunContextUseCase`, `AnalysisContextUseCase`
### Model Conventions
- Calls `full_clean()` before every `save()` to enforce validation
- Calls `refresh_from_db()` after save so prefixed `orcabus_id` values are returned correctly
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
### Viewset Conventions
- `PatchOnlyViewSet` — GET, POST, PATCH (no PUT, no DELETE)
- `PostOnlyViewSet` — GET, POST (no update, no DELETE)
- `NoDeleteViewSet` — GET, POST, PUT, PATCH (no DELETE)
### Serializer Conventions
### Pydantic Event Models
### Import Organization
### Logging
### Error Handling
- Domain exceptions are defined in `app/workflow_manager/errors.py` (`RerunDuplicationError`)
- Django `ValidationError` is the standard for model-level constraint violations
- Pydantic `ValidationError` is used for event schema violations
- Services return `(bool, object)` tuples rather than raising on soft failures (e.g. `update_workflow_run_to_new_state` returns `(success, state)`)
- `FieldError` from bad query params is caught silently and returns `qs.none()`
### API Response Format
### Transactions
## TypeScript Conventions
### File Naming
- Test files: `*.test.ts` under `test/`
- Config files: `jest.config.js`, `tsconfig.json`, `eslint.config.mjs`
### Code Style
- Prettier enforces formatting (`pnpm prettier`)
- ESLint enforces linting (`pnpm lint`)
- TypeScript strict compilation verified before test run (`tsc && jest`)
### Test Style
## Comments
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Two co-deployed Django apps: `workflow_manager` (API + models + DB) and `workflow_manager_proc` (event processing Lambdas)
- All persistent state lives in PostgreSQL (AWS RDS Aurora); no in-memory or cache layer
- Emits downstream events back onto the same EventBridge bus after persisting state changes
- OrcaBus-scoped unique IDs with type-prefixed primary keys (`wfr`, `wfl`, `stt`, `pld`, `anr`, `ana`, etc.)
- Three Lambda event handlers, one WSGI API Lambda, one migration Lambda — all deployed as separate Python functions sharing a common base layer
## Layers
- Purpose: Persistent data representation; single source of truth for all entities
- All models inherit `OrcaBusBaseModel` (`app/workflow_manager/models/base.py`)
- `OrcaBusBaseModel.save()` always calls `full_clean()` then `refresh_from_db()` to enforce validation and reload custom field annotations
- Uses custom `OrcaBusIdField` (`app/workflow_manager/fields.py`) as primary key with type-prefixed IDs
- Custom `OrcaBusBaseManager` provides `get_by_keyword()` for multi-value OR filtering used by viewsets
- Depends on: PostgreSQL via Django ORM
- Used by: viewsets (read), proc services (read/write)
- Purpose: Expose read-only REST API; limited write operations for Workflow and WorkflowRunAction
- Entry point: `app/api.py` → `serverless_wsgi.handle_request` → Django WSGI → `workflow_manager.urls.base`
- `BaseViewSet` is read-only (`ReadOnlyModelViewSet`) — most resources are GET-only
- `WorkflowViewSet` extends `PostOnlyViewSet` (GET + POST, no updates)
- `WorkflowRunActionViewSet` provides POST `/workflowrun/{id}/rerun` and GET `/workflowrun/{id}/validate_rerun_workflows`
- API is camelCase (via `djangorestframework-camel-case` middleware)
- Pagination: `StandardResultsSetPagination` on all lists
- OpenAPI schema generated at `/schema/openapi.json` via `drf-spectacular`
- Depends on: Domain models, serializers, AWS EventBridge (for rerun action)
- Used by: External HTTP clients via API Gateway
- Purpose: React to EventBridge events, persist state, emit downstream events
- Three Lambda handlers, each a thin wrapper that delegates to services
- `domain/event/` contains Pydantic models (`wru.py`, `wrsc.py`, `aru.py`, `arsc.py`) — code-generated from JSON Schema
- `services/` contains business logic separated by entity (workflow_run, analysis_run)
- All service functions decorated with `@transaction.atomic`
- Depends on: Domain models (shared Django ORM), AWS boto3 EventBridge client, `rfc8785` for canonical JSON hashing
- Used by: AWS Lambda (triggered by EventBridge Rules)
- Purpose: CDK stack defining all Lambda functions, EventBridge rules, API Gateway routes, IAM roles
- Written in TypeScript (AWS CDK)
- `stack.ts` defines the `WorkflowManagerStack` with all resources
- `schema.ts` defines EventBridge schema registry publishing
- `lambda-migration/` handles automatic DB migration on deployment
## Data Flow
## State Machine
| Current State | Allowed Next States |
|---------------|---------------------|
| None (new)    | DRAFT (preferred), any (with warning) |
| DRAFT         | DRAFT (payload update), READY |
| READY         | Any non-DRAFT, non-READY |
| RUNNING       | Any non-DRAFT, non-READY; RUNNING only if >1 hour since last RUNNING |
| Terminal (SUCCEEDED, FAILED, ABORTED) | None (blocked) |
| Other         | Any not previously seen |
## Key Abstractions
- Represents a versioned pipeline definition (name + version + code_version + execution_engine)
- Unique constraint: `(name, version, code_version, execution_engine)`
- Has a `validation_state` (UNVALIDATED / VALIDATED / DEPRECATED / FAILED)
- Execution engines: ICA, SEQERA, AWS_BATCH, AWS_ECS, AWS_EKS, Unknown
- File: `app/workflow_manager/models/workflow.py`
- Represents one execution of a Workflow
- Identified by `portal_run_id` (unique, human-readable: `YYYYMMDD` + 8-char UUID)
- Links to: one `Workflow`, optional `AnalysisRun`, many `Library` (via `LibraryAssociation`), many `Readset`, many `RunContext`
- State history kept in separate `State` model (one-to-many)
- File: `app/workflow_manager/models/workflow_run.py`
- Append-only state history for a WorkflowRun
- Fields: `status`, `timestamp`, optional `comment`, optional `Payload` FK
- Unique constraint: `(workflow_run, status, timestamp)`
- File: `app/workflow_manager/models/state.py`
- Stores arbitrary JSON data attached to a State
- Deduplicated by `payload_ref_id` (SHA-256 of RFC8785 canonical JSON)
- File: `app/workflow_manager/models/payload.py`
- Groups multiple Workflows into a logical analysis pipeline
- Links to: many `Workflow`, many `AnalysisContext`
- When an AnalysisRun reaches READY, one WorkflowRun is auto-created per linked Workflow
- File: `app/workflow_manager/models/analysis.py`
- One execution of an Analysis
- Separate state model: `AnalysisRunState` (DRAFT → READY only)
- No Payload attached to AnalysisRunState (unlike WorkflowRun State)
- File: `app/workflow_manager/models/analysis_run.py`
- Compute or storage environment descriptor (e.g., specific AWS account/environment)
- Unique by `(name, usecase)` where usecase is COMPUTE or STORAGE
- File: `app/workflow_manager/models/run_context.py`
- `Status` enum in `app/workflow_manager/models/common.py` normalizes incoming status strings via aliases
- DRAFT aliases: DRAFT, INITIAL, CREATED
- RUNNING aliases: RUNNING, IN_PROGRESS
- SUCCEEDED aliases: SUCCEEDED, SUCCESS
- FAILED aliases: FAILED, FAILURE, FAIL
- ABORTED aliases: ABORTED, CANCELLED, CANCELED
## Event Schema Architecture
- `WorkflowRunUpdate` (WRU) — inbound: `app/workflow_manager_proc/domain/event/wru.py`
- `WorkflowRunStateChange` (WRSC) — outbound: `app/workflow_manager_proc/domain/event/wrsc.py`
- `AnalysisRunUpdate` (ARU) — inbound: `app/workflow_manager_proc/domain/event/aru.py`
- `AnalysisRunStateChange` (ARSC) — outbound: `app/workflow_manager_proc/domain/event/arsc.py`
- `app/workflow_manager/aws_event_bridge/executionservice/workflowrunstatechange/` — inbound WRSC from external execution services
- `app/workflow_manager/aws_event_bridge/workflowmanager/workflowrunstatechange/` — outbound (used by rerun API action)
- WRSC events have an `id` field computed as MD5 of key fields (version, orcabusId, portalRunId, workflowRunName, status, workflow.orcabusId, payload.refId, library IDs, readset IDs, computeEnv, storageEnv)
- ARSC events use similar MD5 hash
- Payload data deduplication: SHA-256 of RFC8785 canonical JSON stored as `payload_ref_id`
## Entry Points
## Error Handling
- Missing required records (Workflow, Analysis): raise exception — triggers Lambda retry
- Duplicate/unchanged state: return `False` from `transition_to()` — logged, no event emitted, Lambda succeeds
- Terminal state transition attempt: return `False` — silently ignored
- Rerun duplication: raises `RerunDuplicationError` → API returns HTTP 400
- State hash mismatch on payload: `assert` raises `AssertionError` → Lambda fails
- Stale events (timestamp earlier than current state): return `False` — silently ignored
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
