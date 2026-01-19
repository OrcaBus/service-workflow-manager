Workflow Manager
================================================================================

[![codecov.io](https://codecov.io/gh/OrcaBus/service-workflow-manager/coverage.svg?branch=main)](https://codecov.io/gh/OrcaBus/service-workflow-manager?branch=main)
[![Pull Request Tests Status](https://github.com/OrcaBus/service-workflow-manager/workflows/Pull%20Request%20Tests/badge.svg)](https://github.com/OrcaBus/service-workflow-manager/actions/workflows/pr-tests.yml)


<!-- TOC -->
- [Workflow Manager](#workflow-manager)
  - [Service Description](#service-description)
    - [Name \& responsibility](#name--responsibility)
    - [Description](#description)
    - [API Endpoints](#api-endpoints)
    - [Consumed Events](#consumed-events)
    - [Published Events](#published-events)
    - [Data Model \& States](#data-model--states)
      - [Data Model](#data-model)
      - [States](#states)
    - [Major Business Rules](#major-business-rules)
    - [Permissions \& Access Control](#permissions--access-control)
  - [Infrastructure \& Deployment](#infrastructure--deployment)
    - [Stateful](#stateful)
    - [Stateless](#stateless)
  - [Development](#development)
    - [Project Structure](#project-structure)
    - [Setup](#setup)
      - [Requirements](#requirements)
      - [Install Dependencies](#install-dependencies)
      - [CDK](#cdk)
      - [Stacks](#stacks)
    - [Conventions](#conventions)
    - [Linting \& Formatting](#linting--formatting)
    - [Testing](#testing)
  - [Glossary \& References](#glossary--references)
<!-- TOC -->

Service Description
--------------------------------------------------------------------------------

### Name & responsibility

### Description

The Workflow Manager Service keeps track of all workflows executed within the OrcaBus platform. It's responsible for tracking and relaying state updates from execution services to OrcaBus platform services.
Only events originating from the Workflow Manager should be consumed by other services and with that the service acts as a gatekeeper/mediator between workflow state emitters and corresponding consumers.

### API Endpoints

The Workflow Manager provides a RESTful API with public documentation in OpenAPI format via a Swagger-UI interface.

Production Endpoint: https://workflow.prod.umccr.org/schema/swagger-ui/

### Consumed Events

| Name / DetailType        | Source                                 | Schema Link                                                     | Description                                                            |
|--------------------------|----------------------------------------|-----------------------------------------------------------------|------------------------------------------------------------------------|
| `WorkflowRunUpdate` | anything but `orcabus.workflowmanager` | [schema](./docs/events/WorkflowRunUpdate/WorkflowRunUpdate.schema.json)  | Consumed to track workflow status changes emitted by execution services |
| `AnalysisRunUpdate`   | anything but `orcabus.workflowmanager` | [schema](./docs/events/AnalysisRunUpdate/AnalysisRunUpdate.schema.json) | Consumed to track requests for AnalysisRun creation                    |

### Published Events

| Name / DetailType        | Source                    | Schema Link                                                       | Description                         |
|--------------------------|---------------------------|-------------------------------------------------------------------|-------------------------------------|
| `WorkflowRunStateChange` | `orcabus.workflowmanager` | [schema](docs/events/WorkflowRunStateChange/WorkflowRunStateChange.schema.json) | Announces WorkflowRun state changes |
| `AnalysisRunStateChange` | `orcabus.workflowmanager` | [schema](docs/events/AnalysisRunStateChange/AnalysisRunStateChange.schema.json) | Announces AnalysiswRun state changes |


### Data Model & States

#### Data Model

See the [entity model](./docs/diagrams/workflow-manager-entity-diagram.drawio.svg) for a high level overview of the service's data model.

#### States

Supported `WorkflowRun` states

| State         | Description                                      |
|---------------|--------------------------------------------------|
| DRAFT         | The initial registration of a `WorkflowRun`. This may only be the intent of execution, way before a decision of execution is / can be made. |
| READY         | The indication that the requirement for execution are fulfilled and execution can proceed. Should include all the data needed to make the "readyness" decission and required for actual workflow execution. |
| RUNNING       | Indicating that the workflow is running / progressing. |
| ABORTED       | Indicating that a `WorkflowRun` was aborted (usually due to manual intervention). |
| FAILED        | Emitted when a `WorkflowRun` execution has failed. |
| SUCCEDED      | Emitted when a `WorkflowRun` execution was successful. Usually taken as the signal for further dependent processes to be activated. |
| DEPRECATED    | Singalling that a successful `WorkflowRun` has been deemed no longer valid / needed and been deprecated. Also, see Workflow deprection [SOP](https://github.com/OrcaBus/wiki/blob/main/operational/SOPs/workflow-run-deprecation.md). |

Supported `AnalysisRun` states

| State         | Description                                      |
|---------------|--------------------------------------------------|
| DRAFT         | The initial registration of an `AnalysisRun`. |
| READY         | Indicating that all requirements and data to start the Analysis are available. |


### Major Business Rules

The Workflow Manager is acting as an interface and gatekeeper for workflow/workload related events. It abstracts the interaction between execution services and orchestration logic allowing servics to remain fairly independent without having to know of each others implementation details.

To that effect the Workflow Manager exposes a set of interfaces that are uses to facilitate those communications: \
`WorkflowRunUpdate` and `AnalysisRunUpdate` events are consumed to ingest change notifications from external services in a predictable and structured format, while `WorkflowRunStateChange` and `AnalysisRunStateChange` are emitted to announce any relevant changes to the OrcaBus platform services in a known and controlled format.

### Permissions & Access Control

Infrastructure & Deployment
--------------------------------------------------------------------------------

Short description with diagrams where appropriate.
Deployment settings / configuration (e.g. CodePipeline(s) / automated builds).

It is recommended to use the automated CI/CD CodePipeline for all cases. Creating a Pull Request (PR) and successful merging will trigger the automated continuous integration (CI) testing pipeline. Once passed, it will continuously deploy (CD) to the target environment.


### Stateful

- Queues
- Buckets
- Database
- ...

### Stateless
- Lambdas
- StepFunctions

Development
--------------------------------------------------------------------------------

### Project Structure

The root of the project is an AWS CDK project where the main application logic lives inside the `./app` folder.
Additional documentation can be found in the `./docs` folder.

### Setup

See also the app specific [README](app/README.md)

#### Requirements

```sh
node --version
v22.15.0

# Update corepack if necessary (from pnpm docs)
npm install --global corepack@latest

# Enable corepack
corepack enable pnpm

```

#### Install Dependencies

To install all required dependencies, run:

```sh
make install
```

#### CDK

You can access CDK commands using the `pnpm` wrapper script. For example:

```sh
pnpm cdk <command>
```

This ensures the correct context is set for CDK to execute.

#### Stacks

The following stacks are managed within this CDK project. The root stack (excluding the `DeploymentPipeline`) deploys a stack in the toolchain account, which then deploys a CodePipeline for cross-environment deployments to `beta`, `gamma`, and `prod`.

To list all stacks, switch to the AWS DEV account (e.g. `export AWS_PROFILE=umccr-dev-admin`) and then run:

```sh
pnpm cdk ls
```

Example output:

```sh
OrcaBusStatelessWorkflowManagerStack
OrcaBusStatelessWorkflowManagerStack/DeploymentPipeline/OrcaBusBeta/WorkflowManagerStack (OrcaBusBeta-WorkflowManagerStack)
OrcaBusStatelessWorkflowManagerStack/DeploymentPipeline/OrcaBusGamma/WorkflowManagerStack (OrcaBusGamma-WorkflowManagerStack)
OrcaBusStatelessWorkflowManagerStack/DeploymentPipeline/OrcaBusProd/WorkflowManagerStack (OrcaBusProd-WorkflowManagerStack)
```

To deploy the CICD pipeline for the workflow manager, switch to the AWS Bastion/Toolchain account (e.g. `export AWS_PROFILE=umccr-bastion-admin`) and then run:
```sh
pnpm cdk synth -e OrcaBusStatelessWorkflowManagerStack
pnpm cdk diff -e OrcaBusStatelessWorkflowManagerStack
pnpm cdk deploy -e OrcaBusStatelessWorkflowManagerStack
```

To deploy the app, switch to the AWS DEV account (e.g. `export AWS_PROFILE=umccr-dev-admin`) and then run:
```sh
pnpm cdk synth -e OrcaBusStatelessWorkflowManagerStack/DeploymentPipeline/OrcaBusBeta/WorkflowManagerStack
pnpm cdk diff -e OrcaBusStatelessWorkflowManagerStack/DeploymentPipeline/OrcaBusBeta/WorkflowManagerStack
pnpm cdk deploy -e OrcaBusStatelessWorkflowManagerStack/DeploymentPipeline/OrcaBusBeta/WorkflowManagerStack
```


### Conventions
### Linting & Formatting

Automated checks are enforces via pre-commit hooks, ensuring only checked code is committed. For details consult the `.pre-commit-config.yaml` file.

Manual, on-demand, checking is also available via `make` targets (see below). For details consult the 'Makefile'.


To run linting and formatting checks on the root project, use:

```sh
make check
```

To automatically fix issues with ESLint and Prettier, run:

```sh
make fix
```

### Testing


Unit tests are available for most of the business logic. Test code is hosted alongside business in `/tests/` directories.

```sh
make test
```

Glossary & References
--------------------------------------------------------------------------------

For general terms and expressions used across OrcaBus services, please see the platform [documentation](https://github.com/OrcaBus/wiki/blob/main/orcabus-platform/README.md#glossary--references).

Service specific terms:

| Term        | Description                                                                                                                                             |
|-------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
|             |                                                                                                                                                         |
