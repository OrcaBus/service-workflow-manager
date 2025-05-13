import * as cdk from 'aws-cdk-lib';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as chatbot from 'aws-cdk-lib/aws-chatbot';
import * as codepipeline from 'aws-cdk-lib/aws-codepipeline';
import * as codestarnotifications from 'aws-cdk-lib/aws-codestarnotifications';
import { Construct } from 'constructs';
import { DeploymentStackPipeline } from '@orcabus/platform-cdk-constructs/deployment-stack-pipeline';
import { WorkflowManagerStack } from '../stage/stack';
import { getWorkflowManagerStackProps } from '../stage/config';

export class StatelessStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const dsp = new DeploymentStackPipeline(this, 'DeploymentPipeline', {
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
    });

    // notification for success/failure
    const alertsBuildSlackConfigArn = ssm.StringParameter.valueForStringParameter(
      this,
      '/chatbot_arn/slack/alerts-build'
    );
    const target = chatbot.SlackChannelConfiguration.fromSlackChannelConfigurationArn(
      this,
      'SlackChannelConfiguration',
      alertsBuildSlackConfigArn
    );

    dsp.pipeline.notifyOn('PipelineSlackNotification', target, {
      events: [
        codepipeline.PipelineNotificationEvents.PIPELINE_EXECUTION_FAILED,
        codepipeline.PipelineNotificationEvents.PIPELINE_EXECUTION_SUCCEEDED,
      ],
      detailType: codestarnotifications.DetailType.FULL,
      notificationRuleName: 'orcabus_workflow_manager_stateless_pipeline_notification',
    });
  }
}
