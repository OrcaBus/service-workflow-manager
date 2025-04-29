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

To list all stacks, run:

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

To test deplot to dev (example)
```sh
pnpm cdk synth -e OrcaBusStatelessWorkflowManagerStack/DeploymentPipeline/OrcaBusBeta/WorkflowManagerStack
pnpm cdk diff -e OrcaBusStatelessWorkflowManagerStack/DeploymentPipeline/OrcaBusBeta/WorkflowManagerStack
pnpm cdk deploy -e OrcaBusStatelessWorkflowManagerStack/DeploymentPipeline/OrcaBusBeta/WorkflowManagerStack
```

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
