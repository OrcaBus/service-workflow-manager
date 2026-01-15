import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { DeploymentStackPipeline } from '@orcabus/platform-cdk-constructs/deployment-stack-pipeline';
import { WorkflowManagerStack } from '../stage/stack';
import { getWorkflowManagerStackProps } from '../stage/config';

export class StatelessStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    new DeploymentStackPipeline(this, 'DeploymentPipeline', {
      githubBranch: 'main',
      githubRepo: 'service-workflow-manager',
      stack: WorkflowManagerStack,
      stackName: 'WorkflowManagerStack',
      stackConfig: {
        beta: getWorkflowManagerStackProps('BETA'),
        gamma: getWorkflowManagerStackProps('GAMMA'),
        prod: getWorkflowManagerStackProps('PROD'),
      },
      pipelineName: 'OrcaBus-StatelessWorkflowManager',
      cdkSynthCmd: ['pnpm install --frozen-lockfile --ignore-scripts', 'pnpm cdk synth'],
      enableSlackNotification: true,
      unitAppTestConfig: {
        command: [
          'cd app',
          'DJANGO_SETTINGS_MODULE=workflow_manager.settings.it DB_PORT=5435 make testaws',
        ],
      },
    });
  }
}
