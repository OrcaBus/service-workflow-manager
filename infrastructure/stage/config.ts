import { getDefaultApiGatewayConfiguration } from '@orcabus/platform-cdk-constructs/api-gateway';
import { StageName } from '@orcabus/platform-cdk-constructs/utils';
import { WorkflowManagerStackProps } from './stack';
import { VpcLookupOptions } from 'aws-cdk-lib/aws-ec2';

export const getWorkflowManagerStackProps = (stage: StageName): WorkflowManagerStackProps => {
  // upstream infra: vpc
  const vpcName = 'main-vpc';
  const vpcStackName = 'networking';
  const vpcProps: VpcLookupOptions = {
    vpcName: vpcName,
    tags: {
      Stack: vpcStackName,
    },
  };

  const computeSecurityGroupName = 'OrcaBusSharedComputeSecurityGroup';
  const eventBusName = 'OrcaBusMain';

  return {
    vpcProps,
    lambdaSecurityGroupName: computeSecurityGroupName,
    mainBusName: eventBusName,
    apiGatewayCognitoProps: {
      ...getDefaultApiGatewayConfiguration(stage),
      apiName: 'WorkflowManager',
      customDomainNamePrefix: 'workflow-dev-deploy',
    },
  };
};
