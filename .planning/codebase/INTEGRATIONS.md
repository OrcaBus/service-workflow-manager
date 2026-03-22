# External Integrations

> Generated: 2026-03-23
> Focus: External services, APIs, databases, message queues, cloud services, third-party dependencies

## Databases

**Primary Database: PostgreSQL (AWS Aurora)**
- Provider: AWS Aurora PostgreSQL (version aligned to LTS — PostgreSQL 16 locally via Docker)
- Database name: `workflow_manager`
- DB user: `workflow_manager`
- Connection (production): IAM authentication via `django-iam-dbauth` with SSL required
  - Engine: `django_iam_dbauth.aws.postgresql`
  - Options: `use_iam_auth: True`, `sslmode: "require"`
  - Config: `app/workflow_manager/settings/aws.py`
  - Env vars: `PG_HOST`, `PG_USER`, `PG_DB_NAME`
- Connection (local/test): standard psycopg3 with username/password
  - Host/port via env vars `DB_HOSTNAME`, `DB_PORT` (defaults: `localhost:5432` / `localhost:5435` for tests)
  - Config: `app/workflow_manager/settings/local.py`, `app/workflow_manager/settings/it.py`
- CDK cluster access: `DatabaseCluster.fromDatabaseClusterAttributes` using SSM parameters
  - SSM param for host: `DB_CLUSTER_ENDPOINT_HOST_PARAMETER_NAME` (from `@orcabus/platform-cdk-constructs`)
  - SSM param for resource ID: `DB_CLUSTER_RESOURCE_ID_PARAMETER_NAME` (from `@orcabus/platform-cdk-constructs`)
  - Cluster identifier: `DB_CLUSTER_IDENTIFIER` (from `@orcabus/platform-cdk-constructs`)

**Local Development Database:**
- Docker image: `public.ecr.aws/docker/library/postgres:16`
- Container name: `orcabus_db`
- Compose file: `app/compose_local.yml`
- Init script: `app/init-db.sql`

## Message Bus / Event Integration

**AWS EventBridge**
- Bus name: resolved from `EVENT_BUS_NAME` environment variable (set from `@orcabus/platform-cdk-constructs/shared-config/event-bridge`)
- Event source: `orcabus.workflowmanagerapi` (emitted by API handlers)
- Emission library: `libumccr.aws.libeb.emit_event` (`app/workflow_manager/aws_event_bridge/event.py`)

**Incoming Event Rules (subscribed via CDK EventBridge Rules):**

| Detail Type | Rule Condition | Lambda Handler |
|---|---|---|
| `WorkflowRunStateChange` | Source NOT `orcabus.workflowmanager`, fields `workflowName` + `workflowVersion` exist | `app/workflow_manager_proc/lambdas/handle_wrsc_event_legacy.py` |
| `WorkflowRunUpdate` | Source NOT `orcabus.workflowmanager` | `app/workflow_manager_proc/lambdas/handle_wru_event.py` |
| `AnalysisRunUpdate` | Source NOT `orcabus.workflowmanager` | `app/workflow_manager_proc/lambdas/handle_aru_event.py` |

**Outgoing Events (emitted by this service):**

| Event Type | Detail Type | Source |
|---|---|---|
| Workflow run state change | `WorkflowRunStateChange` | `orcabus.workflowmanagerapi` |
| Analysis run state change | `AnalysisRunStateChange` | `orcabus.workflowmanagerapi` |

**EventBridge Schema Registry:**
- Registry name: from `EVENT_SCHEMA_REGISTRY_NAME` (`@orcabus/platform-cdk-constructs`)
- Published schemas (JSONSchemaDraft4):
  - `orcabus.workflowmanager@WorkflowRunStateChange` — `docs/events/WorkflowRunStateChange/WorkflowRunStateChange.schema.json`
  - `orcabus.workflowmanager@WorkflowRunUpdate` — `docs/events/WorkflowRunUpdate/WorkflowRunUpdate.schema.json`
  - `orcabus.workflowmanager@AnalysisRunStateChange` — `docs/events/AnalysisRunStateChange/AnalysisRunStateChange.schema.json`
  - `orcabus.workflowmanager@AnalysisRunUpdate` — `docs/events/AnalysisRunUpdate/AnalysisRunUpdate.schema.json`
- CDK schema construct: `infrastructure/stage/schema.ts`

## API Gateway

**AWS API Gateway v2 (HTTP API)**
- Construct: `OrcaBusApiGateway` from `@orcabus/platform-cdk-constructs/api-gateway`
- API name: `WorkflowManager`
- Custom domain prefix: `workflow`
- Cognito authentication: applied to all routes except schema endpoints
- Auth-exempt routes: `GET /schema/{PROXY+}` (uses `HttpNoneAuthorizer`)
- Auth-required special route: `POST /api/v1/workflowrun/{orcabusId}/rerun/{proxy+}` (uses `wfmApi.authStackHttpLambdaAuthorizer`)
- Backend integration: `HttpLambdaIntegration` pointing to the API Lambda function
- CDK configuration: `infrastructure/stage/stack.ts` → `createApiHandlerAndIntegration()`
- CORS allowed origins (production): `portal.umccr.org`, `portal.prod.umccr.org`, `portal.stg.umccr.org`, `portal.dev.umccr.org`, `orcaui.umccr.org`, `orcaui.prod.umccr.org`, `orcaui.dev.umccr.org`, `orcaui.stg.umccr.org`

## AWS Lambda

**Deployed functions (all ARM64, Python 3.12, 1024 MB):**
- `Api` — Django WSGI handler via `serverless-wsgi`; entry: `app/api.py`; timeout: 28s
- `Migration` — Django migration runner; entry: `app/migrate.py`; timeout: 5 minutes; auto-triggered on deploy
- `HandleWrscEventLegacy` — Processes legacy `WorkflowRunStateChange` events; entry: `app/workflow_manager_proc/lambdas/handle_wrsc_event_legacy.py`; timeout: 28s
- `HandleWruEvent` — Processes `WorkflowRunUpdate` events; entry: `app/workflow_manager_proc/lambdas/handle_wru_event.py`; timeout: 28s
- `HandleAruEvent` — Processes `AnalysisRunUpdate` events; entry: `app/workflow_manager_proc/lambdas/handle_aru_event.py`; timeout: 28s

**Lambda Layer:**
- `BaseLayer` — Python dependency layer built from `app/deps/` (requirements.txt)
- Compatible: ARM64, Python 3.12

**Lambda networking:**
- All functions deployed inside a VPC (`VPC_LOOKUP_PROPS` from platform constructs)
- Security group: `SHARED_SECURITY_GROUP_NAME` from platform constructs
- Subnets: private subnets only

**Lambda IAM Role permissions:**
- `AWSLambdaBasicExecutionRole` (managed policy)
- `AWSLambdaVPCAccessExecutionRole` (managed policy)
- `AmazonSSMReadOnlyAccess` (managed policy — reads DB endpoint from SSM)
- RDS IAM connect for `workflow_manager` user
- EventBridge `PutEvents` on main bus (all Lambda functions)

## AWS Systems Manager (SSM Parameter Store)

**Read at deploy time (CDK synth):**
- `DB_CLUSTER_RESOURCE_ID_PARAMETER_NAME` — Aurora cluster resource ID
- `DB_CLUSTER_ENDPOINT_HOST_PARAMETER_NAME` — Aurora cluster endpoint hostname

**Read at Lambda runtime (via IAM):**
- SSM parameters referenced by shared platform constructs for VPC, networking

## AWS X-Ray

- SDK: `aws-xray-sdk` (Python, no pinned version)
- Django middleware: `aws_xray_sdk.ext.django.middleware.XRayMiddleware` (enabled in `MIDDLEWARE`)
- Tracing name: env var `AWS_XRAY_TRACING_NAME` (default: `workflow_manager`)
- SDK disabled by default locally; enabled at Lambda runtime via `AWS_XRAY_SDK_ENABLED=true`
- Config: `app/workflow_manager/settings/base.py`

## AWS S3

**Local Development Only:**
- DB dump backup bucket: `s3://orcabus-pg-dd-843407916570-ap-southeast-2/pg-dd/`
- Used by `make s3-load` / `make db-init` to restore local development database from production snapshots
- Requires AWS profile `dev` with appropriate permissions
- No S3 usage in production Lambda code

## CI/CD Pipeline

**Provider:** AWS CDK Pipelines (`DeploymentStackPipeline` from `@orcabus/platform-cdk-constructs`)
- Pipeline name: `OrcaBus-StatelessWorkflowManager`
- Source: GitHub repo `OrcaBus/service-workflow-manager`, branch `main`
- Stages: BETA → GAMMA → PROD (via `getWorkflowManagerStackProps`)
- Synth commands: `pnpm install --frozen-lockfile --ignore-scripts && pnpm cdk synth`
- Unit/app test command: `cd app && DJANGO_SETTINGS_MODULE=workflow_manager.settings.it DB_PORT=5435 make test-aws`
- Slack notifications: enabled
- CDK stack: `infrastructure/toolchain/stateless-stack.ts`

## Authentication

**Production API Authentication:**
- Cognito-based auth via `OrcaBusApiGateway` / `authStackHttpLambdaAuthorizer` (platform construct)
- DB authentication: AWS IAM (`django-iam-dbauth`) — no static DB passwords in production
- REST framework token auth also configured: `rest_framework.authentication.TokenAuthentication`

## Monitoring & Observability

**Error Tracking:** None (no Sentry or equivalent detected)

**Distributed Tracing:** AWS X-Ray (via `aws-xray-sdk`)

**Logging:**
- Python: `logging.StreamHandler` to stdout, INFO level by default (`app/workflow_manager/settings/base.py`)
- Consumed by AWS CloudWatch Logs automatically from Lambda stdout

## File Storage

- No file storage integration detected (local filesystem only for dumps during development)

## Caching

- `cachetools 6.2.4` is installed but no external cache service (Redis/Memcached) is configured

---

*Integration audit: 2026-03-23*
