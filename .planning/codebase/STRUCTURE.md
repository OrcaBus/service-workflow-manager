# Codebase Structure
> Generated: 2026-03-23
> Focus: Directory layout, key files, what lives where, entry points, configuration

## Directory Layout

```
service-workflow-manager/
├── app/                            # All Python application code
│   ├── api.py                      # API Lambda entry point (WSGI bridge)
│   ├── migrate.py                  # Migration Lambda entry point
│   ├── manage.py                   # Django management CLI
│   ├── Dockerfile                  # Container image for local dev
│   ├── compose_local.yml           # Docker Compose for local dev
│   ├── compose_test.yml            # Docker Compose for test runs
│   ├── deps/                       # Lambda layer dependencies
│   │   ├── requirements.txt        # Production dependencies
│   │   ├── requirements-dev.txt    # Dev-only dependencies
│   │   └── requirements-test.txt  # Test dependencies
│   ├── workflow_manager/           # Main Django app (API + models)
│   │   ├── models/                 # ORM models
│   │   ├── viewsets/               # DRF viewsets (API handlers)
│   │   ├── serializers/            # DRF serializers
│   │   ├── urls/                   # URL routing
│   │   ├── settings/               # Django settings by environment
│   │   ├── migrations/             # Django DB migrations
│   │   ├── aws_event_bridge/       # Legacy event schema definitions
│   │   ├── management/commands/    # Django management commands
│   │   ├── tests/                  # API/model unit tests
│   │   ├── fields.py               # Custom OrcaBusIdField
│   │   ├── pagination.py           # Pagination classes
│   │   ├── routers.py              # Custom DRF router
│   │   ├── errors.py               # Custom exception classes
│   │   └── wsgi.py                 # WSGI application
│   └── workflow_manager_proc/      # Event processing app (Lambda handlers)
│       ├── lambdas/                # Lambda handler entry points
│       ├── domain/event/           # Pydantic event schemas (code-generated)
│       ├── services/               # Business logic services
│       └── tests/                  # Proc unit and integration tests
├── infrastructure/                 # AWS CDK infrastructure (TypeScript)
│   ├── stage/
│   │   ├── stack.ts                # Main CDK stack definition
│   │   ├── schema.ts               # EventBridge schema registry
│   │   ├── config.ts               # Environment/stage configuration
│   │   └── lambda-migration/       # Auto-trigger migration construct
│   └── toolchain/                  # CDK pipeline/toolchain stack
├── docs/                           # Event schema documentation
│   ├── events/
│   │   ├── WorkflowRunStateChange/ # WRSC schema + examples
│   │   ├── WorkflowRunUpdate/      # WRU schema + examples
│   │   ├── AnalysisRunStateChange/ # ARSC schema + examples
│   │   └── AnalysisRunUpdate/      # ARU schema + examples
│   └── diagrams/                   # Architecture diagrams
├── test/                           # CDK infrastructure tests
├── bin/                            # CDK app entry point
├── cdk.json                        # CDK configuration
├── package.json                    # Node.js/CDK dependencies
├── pnpm-workspace.yaml             # pnpm workspace
├── tsconfig.json                   # TypeScript configuration
├── jest.config.js                  # Jest config for CDK tests
├── Makefile                        # Build/dev convenience targets
└── README.md
```

---

## Key File Locations

**Lambda Entry Points:**
- `app/api.py` — REST API (WSGI → Lambda bridge)
- `app/migrate.py` — Database migration trigger
- `app/workflow_manager_proc/lambdas/handle_wru_event.py` — WorkflowRunUpdate handler
- `app/workflow_manager_proc/lambdas/handle_aru_event.py` — AnalysisRunUpdate handler
- `app/workflow_manager_proc/lambdas/handle_wrsc_event_legacy.py` — Legacy WRSC handler

**Django Configuration:**
- `app/workflow_manager/settings/base.py` — Base settings (all environments)
- `app/workflow_manager/settings/aws.py` — Production/AWS settings
- `app/workflow_manager/settings/local.py` — Local development settings
- `app/workflow_manager/settings/it.py` — Integration test settings
- `app/workflow_manager/urls/base.py` — URL router (all REST endpoints registered here)

**Domain Models:**
- `app/workflow_manager/models/workflow.py` — `Workflow` model (prefix: `wfl`)
- `app/workflow_manager/models/workflow_run.py` — `WorkflowRun` + `LibraryAssociation` models (prefix: `wfr`)
- `app/workflow_manager/models/state.py` — `State` model (prefix: `stt`)
- `app/workflow_manager/models/payload.py` — `Payload` model (prefix: `pld`)
- `app/workflow_manager/models/analysis.py` — `Analysis` model (prefix: `ana`)
- `app/workflow_manager/models/analysis_run.py` — `AnalysisRun` model (prefix: `anr`)
- `app/workflow_manager/models/analysis_run_state.py` — `AnalysisRunState` model (prefix: `ars`)
- `app/workflow_manager/models/library.py` — `Library` model (prefix: `lib`)
- `app/workflow_manager/models/readset.py` — `Readset` model (prefix: `fqr`)
- `app/workflow_manager/models/run_context.py` — `RunContext` model (prefix: `rnx`)
- `app/workflow_manager/models/analysis_context.py` — `AnalysisContext` model
- `app/workflow_manager/models/common.py` — `Status` enum with aliasing logic
- `app/workflow_manager/models/utils.py` — `WorkflowRunUtil` (state machine) + `StateUtil` + `create_portal_run_id()`
- `app/workflow_manager/models/base.py` — `OrcaBusBaseModel` + `OrcaBusBaseManager`
- `app/workflow_manager/fields.py` — `OrcaBusIdField` custom primary key field

**Viewsets (API Handlers):**
- `app/workflow_manager/viewsets/base.py` — `BaseViewSet`, `PatchOnlyViewSet`, `PostOnlyViewSet`, `NoDeleteViewSet`
- `app/workflow_manager/viewsets/workflow_run.py` — `WorkflowRunViewSet` (read-only; custom filtering)
- `app/workflow_manager/viewsets/workflow_run_action.py` — `WorkflowRunActionViewSet` (rerun action)
- `app/workflow_manager/viewsets/workflow.py` — `WorkflowViewSet` (POST + GET)
- `app/workflow_manager/viewsets/analysis_run.py` — `AnalysisRunViewSet`
- `app/workflow_manager/viewsets/analysis.py` — `AnalysisViewSet`
- `app/workflow_manager/viewsets/state.py` — `StateViewSet` (nested under workflowrun)
- `app/workflow_manager/viewsets/payload.py` — `PayloadViewSet`
- `app/workflow_manager/viewsets/library.py` — `LibraryViewSet`
- `app/workflow_manager/viewsets/run_context.py` — `RunContextViewSet`
- `app/workflow_manager/viewsets/comment.py` — `CommentViewSet`, `AnalysisRunCommentViewSet`
- `app/workflow_manager/viewsets/workflow_run_stats.py` — `WorkflowRunStatsViewSet`
- `app/workflow_manager/viewsets/analysis_context.py` — `AnalysisContextViewSet`

**Event Processing Services:**
- `app/workflow_manager_proc/services/workflow_run.py` — Core WRU processing logic, WRSC event construction
- `app/workflow_manager_proc/services/workflow_run_legacy.py` — Legacy WRSC processing
- `app/workflow_manager_proc/services/analysis_run.py` — ARU processing, ARSC construction, WorkflowRun auto-creation
- `app/workflow_manager_proc/services/analysis_run_utils.py` — Auto-create WorkflowRuns from AnalysisRun READY event
- `app/workflow_manager_proc/services/event_utils.py` — `emit_event()`, `hash_payload_data()`, boto3 EventBridge client

**Event Domain Models (Pydantic, code-generated):**
- `app/workflow_manager_proc/domain/event/wru.py` — WorkflowRunUpdate inbound schema
- `app/workflow_manager_proc/domain/event/wrsc.py` — WorkflowRunStateChange outbound schema
- `app/workflow_manager_proc/domain/event/aru.py` — AnalysisRunUpdate inbound schema
- `app/workflow_manager_proc/domain/event/arsc.py` — AnalysisRunStateChange outbound schema

**Legacy Event Bridge Schemas:**
- `app/workflow_manager/aws_event_bridge/executionservice/workflowrunstatechange/` — Inbound legacy WRSC from execution services
- `app/workflow_manager/aws_event_bridge/workflowmanager/workflowrunstatechange/` — Outbound legacy WRSC (used by rerun API)
- `app/workflow_manager/aws_event_bridge/event.py` — `emit_wrsc_api_event()` for API-triggered events

**Infrastructure:**
- `infrastructure/stage/stack.ts` — Complete AWS resource definitions (Lambdas, EventBridge rules, API Gateway, IAM)
- `infrastructure/stage/schema.ts` — EventBridge schema registry
- `infrastructure/stage/config.ts` — Per-environment configuration values
- `infrastructure/stage/lambda-migration/` — CDK custom resource for auto-migration on deploy

**Test Fixtures and Utilities:**
- `app/workflow_manager/tests/fixtures/` — Django test fixtures (JSON)
- `app/workflow_manager_proc/tests/fixtures/` — Lambda test event fixtures
- `app/workflow_manager/management/commands/` — Django management commands
- `app/generate_mock_workflow_run.py` — CLI helper to generate mock WorkflowRun events
- `app/generate_mock_analysis_run.py` — CLI helper to generate mock AnalysisRun events
- `app/clean_db.py` — DB cleanup utility

---

## Directory Purposes

**`app/workflow_manager/models/`:**
- Every persistent entity has its own file
- All model files import from `base.py` for `OrcaBusBaseModel` and `OrcaBusBaseManager`
- `common.py` contains `Status` — shared across model files and proc services
- `utils.py` contains `WorkflowRunUtil` state machine — the most critical business logic file

**`app/workflow_manager/viewsets/`:**
- One file per resource; most extend `BaseViewSet` (read-only)
- `base.py` defines four base viewset classes with different HTTP method permissions
- `workflow_run.py` is the most complex viewset — has custom `get_queryset()` with time filtering, status filtering, ordering

**`app/workflow_manager/serializers/`:**
- Mirror viewsets — one serializer file per model
- `base.py` contains shared serializer utilities including `version_sort_key`

**`app/workflow_manager/settings/`:**
- `base.py` — shared settings; never used directly in production
- `aws.py` — extends base; reads DB connection from RDS IAM auth and SSM
- `local.py` — extends base; uses local PostgreSQL
- `it.py` — extends base; integration test configuration

**`app/workflow_manager_proc/domain/event/`:**
- Contains only Pydantic model files generated from JSON Schema definitions
- Do not edit manually — regenerate from schemas in `docs/events/`
- `__init__.py` is empty (no re-exports)

**`app/workflow_manager_proc/services/`:**
- Contains all stateful business logic
- Functions are module-level (not class-based)
- All DB-writing functions are `@transaction.atomic`
- `event_utils.py` is the single place for emitting to EventBridge

**`app/deps/`:**
- Python dependency definitions for the Lambda layer
- Shared across all Lambda functions via `PythonLayerVersion`
- `requirements.txt` = production deps loaded into the layer
- `requirements-dev.txt` and `requirements-test.txt` = local development only

**`infrastructure/stage/`:**
- TypeScript CDK code; compiled separately from Python app
- `stack.ts` is the sole definition of deployed AWS resources
- Each Lambda function points to a specific Python file path as its index

---

## Naming Conventions

**Files:**
- Python model files: `snake_case`, one entity per file (e.g., `workflow_run.py`, `analysis_run_state.py`)
- Lambda handlers: `handle_{event_type}_event.py` (e.g., `handle_wru_event.py`)
- Service files: named after the entity they manage (e.g., `workflow_run.py`, `analysis_run.py`)
- Pydantic domain event files: short event-type acronym (e.g., `wru.py`, `wrsc.py`, `aru.py`, `arsc.py`)

**OrcaBus ID Prefixes:**
- `wfl` — Workflow
- `wfr` — WorkflowRun
- `stt` — State
- `pld` — Payload
- `ana` — Analysis
- `anr` — AnalysisRun
- `ars` — AnalysisRunState
- `lib` — Library
- `fqr` — Readset (FASTQ read set)
- `rnx` — RunContext

**Django Apps:**
- `workflow_manager` — the installable Django app (in `INSTALLED_APPS`)
- `workflow_manager_proc` — not a Django app (no `AppConfig`); uses `django.setup()` at Lambda bootstrap

---

## Where to Add New Code

**New persistent entity:**
- Model: `app/workflow_manager/models/{entity}.py` extending `OrcaBusBaseModel`
- Serializer: `app/workflow_manager/serializers/{entity}.py`
- Viewset: `app/workflow_manager/viewsets/{entity}.py` extending appropriate base
- Register in: `app/workflow_manager/urls/base.py`
- Migration: run `python manage.py makemigrations`

**New event type to consume:**
- Add Pydantic schema: `app/workflow_manager_proc/domain/event/{acronym}.py`
- Add service logic: `app/workflow_manager_proc/services/{entity}.py`
- Add Lambda handler: `app/workflow_manager_proc/lambdas/handle_{type}_event.py`
- Add CDK EventBridge Rule + Lambda in: `infrastructure/stage/stack.ts`

**New API endpoint on existing resource:**
- Add `@action` decorator to the relevant viewset in `app/workflow_manager/viewsets/`
- No URL registration needed (DRF router auto-discovers actions)

**New business logic on WorkflowRun state:**
- State machine lives in `app/workflow_manager/models/utils.py::WorkflowRunUtil.transition_to()`
- Extend allowed transitions there; do not add state logic in viewsets or Lambdas

**New outbound event:**
- Add Pydantic model to `app/workflow_manager_proc/domain/event/`
- Add `EventType` enum value in `app/workflow_manager_proc/services/event_utils.py`
- Call `emit_event()` from the relevant service function

**Tests:**
- Model/API tests: `app/workflow_manager/tests/`
- Proc/Lambda tests: `app/workflow_manager_proc/tests/`
- Fixtures: `app/workflow_manager/tests/fixtures/` or `app/workflow_manager_proc/tests/fixtures/`
