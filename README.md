Workflow Manager
================================================================================

<!-- TOC -->
* [Workflow Manager](#workflow-manager)
  * [Service Description](#service-description)
    * [Name & responsibility](#name--responsibility)
    * [Description](#description)
    * [API Endpoints](#api-endpoints)
    * [Consumed Events](#consumed-events)
    * [Published Events](#published-events)
    * [(Internal) Data states & persistence model](#internal-data-states--persistence-model)
    * [Major Business Rules](#major-business-rules)
    * [Permissions & Access Control](#permissions--access-control)
  * [Infrastructure & Deployment](#infrastructure--deployment-)
    * [Stateful](#stateful)
    * [Stateless](#stateless)
  * [Development](#development)
    * [Project Structure](#project-structure)
    * [Setup](#setup)
      * [Requirements](#requirements)
      * [Install Dependencies](#install-dependencies)
      * [CDK](#cdk)
      * [Stacks](#stacks)
    * [Conventions](#conventions)
    * [Linting & Formatting](#linting--formatting)
    * [Testing](#testing)
  * [Glossary & References](#glossary--references)
<!-- TOC -->

Service Description
--------------------------------------------------------------------------------

### Name & responsibility
### Description

The Workflow Manager Service keeps track of all workflows executed within the OrcaBus platform. It's responsible for tracking and relaying state updates from execution services to OrcaBus platform services. 
Only events originating from the Workflow Manager should be consumed by other services and with that the service acts as a gatekeeper/mediator between workflow state emitters and corresponding consumers.

### API Endpoints

The Workflow Manager provides a RESTful API with public documentation in OpenAPI format via a Swagger-UI interface.

Endpoint: https://workflow.prod.umccr.org/schema/swagger-ui/

### Consumed Events

| Name / DetailType        | Source                                 | Schema Link                                                     | Description                                                            |
|--------------------------|----------------------------------------|-----------------------------------------------------------------|------------------------------------------------------------------------|
| `WorkflowRunStateChange` | anything but `orcabus.workflowmanager` | <schema link>                                                   | Consumed to track workflow state changes emitted by execution services |
| `AnalysisRunInitiated`   | ??                                     | [schema](docs/events/AnalysisRunInitiated/AnalysisRunInitiated.schema.json) | Consumed to track requests for AnalysisRun creation                    |
| `AnalysisRunFinalised`   | ??                                     | [schema](docs/events/AnalysisRunFinalised/AnalysisRunFinalised.schema.json) | Consumed to track requests for finalisation of an AnalysisRun          |

### Published Events

| Name / DetailType        | Source                    | Schema Link                                                       | Description                         |
|--------------------------|---------------------------|-------------------------------------------------------------------|-------------------------------------|
| `WorkflowRunStateChange` | `orcabus.workflowmanager` | [schema](docs/events/WorkflowRunStateChange/WorkflowRunStateChange.schema.json) | Announces WorkflowRun state changes |
| `AnalysisRunStateChange` | `orcabus.workflowmanager` | [schema](docs/events/AnalysisRunStateChange/AnalysisRunStateChange.schema.json) | Announces AnalysiswRun state changes |


### (Internal) Data states & persistence model
### Major Business Rules
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
