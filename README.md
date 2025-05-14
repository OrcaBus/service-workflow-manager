# Workflow Manager Stack

## Overview

The root of the project is an AWS CDK project where the main application logic lives inside the `./app` folder.

## Setup

### Requirements

```sh
node --version
v22.15.0

# Update corepack if necessary (from pnpm docs)
npm install --global corepack@latest

# Enable corepack
corepack enable pnpm

```

### Install Dependencies

To install all required dependencies, run:

```sh
make install
```

### CDK Commands

You can access CDK commands using the `pnpm` wrapper script. For example:

```sh
pnpm cdk <command>
```

This ensures the correct context is set for CDK to execute.

### Stacks

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

## Deploy

It is recommended to use the automated CI/CD CodePipeline for all cases. Creating a Pull Request (PR) and successful merging will trigger the automated continuous integration (CI) testing pipeline. Once passed, it will continuously deploy (CD) to the target environment.

## Linting and Formatting

### Run Checks

To run linting and formatting checks on the root project, use:

```sh
make check
```

### Fix Issues

To automatically fix issues with ESLint and Prettier, run:

```sh
make fix
```
