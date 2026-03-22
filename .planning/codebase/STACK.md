# Technology Stack

> Generated: 2026-03-23
> Focus: Languages, frameworks, key libraries, build tools, runtime requirements, package versions

## Languages

**Primary:**
- Python 3.12 — Application logic, Lambda handlers, Django app (`app/`)
- TypeScript 5.9.3 — CDK infrastructure definitions (`infrastructure/`)

**Secondary:**
- SQL — PostgreSQL migration scripts (`app/workflow_manager/migrations/`, `app/init-db.sql`)

## Runtime

**Python Environment:**
- Python 3.12 (specified in `app/Dockerfile`: `public.ecr.aws/docker/library/python:3.12`)
- AWS Lambda runtime: `aws_lambda.Runtime.PYTHON_3_12` with `Architecture.ARM_64`

**Node/CDK Environment:**
- Package manager: pnpm 10.30.2 (declared in `package.json` `packageManager` field)
- Lockfile: `pnpm-lock.yaml` present

## Python Frameworks & Libraries

**Web Framework:**
- Django 5.2.12 — Core web framework (`app/deps/requirements.txt`)
- djangorestframework 3.16.1 — REST API layer
- djangorestframework-camel-case 1.4.2 — JSON camelCase transformation for API I/O
- drf-spectacular 0.29.0 — OpenAPI schema generation

**Database:**
- psycopg[binary] 3.3.2 — PostgreSQL adapter (psycopg3)
- django-iam-dbauth 0.2.1 — AWS IAM authentication for PostgreSQL in production

**HTTP/WSGI:**
- serverless-wsgi 3.1.0 — Bridges Django WSGI app to AWS Lambda events (`app/api.py`)
- Werkzeug 3.1.5 — WSGI utilities (used by `runserver_plus`)

**AWS Integration:**
- aws-xray-sdk — Distributed tracing (no pinned version; latest used)
- boto3 — AWS SDK (unpinned in test deps; Lambda runtime provides it in production)

**Data Validation & Serialization:**
- pydantic 2.12.5 — Event schema validation for domain models (`app/workflow_manager_proc/domain/event/`)
- rfc8785 0.1.4 — JSON Canonicalization Scheme for state hashing/deduplication

**Identifiers:**
- ulid-py 1.1.0 — ULID generation for `OrcaBusIdField` (`app/workflow_manager/fields.py`)

**Utilities:**
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

**Code Style:**
- black (Python formatter, target py312, invoked via `make lint`)

## CDK / Infrastructure Frameworks

**Core:**
- aws-cdk-lib 2.240.0+ — Core CDK library (`package.json`)
- aws-cdk 2.1107.0+ — CDK CLI (dev dependency)
- @aws-cdk/aws-lambda-python-alpha 2.234.1-alpha.0 — `PythonFunction` and `PythonLayerVersion` constructs
- constructs 10.5.1+ — CDK construct base
- @orcabus/platform-cdk-constructs 1.0.2 — Shared OrcaBus platform constructs (API Gateway, deployment pipeline, shared config)
- cdk-nag 2.37.55 — CDK security/compliance checks

**CDK Dev Tools:**
- ts-jest 29.4.6 — TypeScript test runner for Jest
- jest 30.2.0 — JavaScript test runner
- typescript-eslint 8.56.1 — TypeScript linting
- eslint 10.0.2 — JavaScript/TypeScript linter
- prettier 3.8.1 — Code formatter
- ts-node 10.9.2 — TypeScript execution for CDK entrypoint

## Build Tools

**Infrastructure:**
- `pnpm cdk synth` — Synthesizes CloudFormation from TypeScript CDK
- Entry point: `bin/deploy.ts` (invoked via `pnpx ts-node`)
- TypeScript compiler options: ES2020 target, CommonJS modules, strict mode enabled (`tsconfig.json`)

**Application:**
- `make install` — Installs Python deps via pip from `deps/requirements-dev.txt`
- `python manage.py migrate` — Applies Django migrations
- Docker: `public.ecr.aws/docker/library/python:3.12` base image

## Configuration

**Environment Variables (application):**
- `DJANGO_SETTINGS_MODULE` — Selects settings module (`workflow_manager.settings.local` / `.it` / `.aws`)
- `EVENT_BUS_NAME` — AWS EventBridge bus name
- `PG_HOST` — PostgreSQL host (production)
- `PG_USER` — PostgreSQL user (production)
- `PG_DB_NAME` — PostgreSQL database name (production)
- `AWS_XRAY_CONTEXT_MISSING` — X-Ray context missing behavior
- `AWS_XRAY_TRACING_NAME` — X-Ray service name
- `DJANGO_SECRET_KEY` — Django secret key
- `DJANGO_DEBUG` — Debug mode flag

**Settings Modules:**
- `workflow_manager.settings.local` — Local development (SQLite-style path default)
- `workflow_manager.settings.it` — Integration tests (PostgreSQL, configurable host/port)
- `workflow_manager.settings.aws` — Production AWS (IAM auth PostgreSQL, CORS restricted)

**Build Config Files:**
- `tsconfig.json` — TypeScript compiler configuration
- `eslint.config.mjs` — ESLint flat config
- `jest.config.js` — Jest configuration
- `cdk.json` — CDK app entrypoint and context
- `pnpm-workspace.yaml` — pnpm workspace + dependency overrides

## Platform Requirements

**Development:**
- Docker + Docker Compose (PostgreSQL 16 via `public.ecr.aws/docker/library/postgres:16`)
- Python 3.12
- Node.js (compatible with pnpm 10.x)
- pnpm 10.30.2
- AWS CLI (optional, for S3 DB dump downloads)

**Production Deployment Target:**
- AWS Lambda (ARM64, Python 3.12)
- Deployed via AWS CDK pipeline (`OrcaBus-StatelessWorkflowManager`)
- Stages: BETA, GAMMA, PROD
- GitHub repo: `OrcaBus/service-workflow-manager`, branch: `main`

---

*Stack analysis: 2026-03-23*
