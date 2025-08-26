import path from 'path';
import { Construct } from 'constructs';
import { Architecture } from 'aws-cdk-lib/aws-lambda';
import { ISecurityGroup, IVpc, SecurityGroup, Vpc, VpcLookupOptions } from 'aws-cdk-lib/aws-ec2';
import { EventBus, IEventBus, Rule } from 'aws-cdk-lib/aws-events';
import { aws_events_targets, aws_lambda, Duration, Stack, StackProps } from 'aws-cdk-lib';
import { PythonFunction, PythonLayerVersion } from '@aws-cdk/aws-lambda-python-alpha';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import {
  HttpMethod,
  HttpNoneAuthorizer,
  HttpRoute,
  HttpRouteKey,
} from 'aws-cdk-lib/aws-apigatewayv2';
import { ManagedPolicy, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import {
  OrcaBusApiGateway,
  OrcaBusApiGatewayProps,
} from '@orcabus/platform-cdk-constructs/api-gateway';
import { DatabaseCluster } from 'aws-cdk-lib/aws-rds';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import {
  DB_CLUSTER_ENDPOINT_HOST_PARAMETER_NAME,
  DB_CLUSTER_IDENTIFIER,
  DB_CLUSTER_RESOURCE_ID_PARAMETER_NAME,
} from '@orcabus/platform-cdk-constructs/shared-config/database';
import { WorkflowManagerSchemaRegistry } from './schema';

export interface WorkflowManagerStackProps extends StackProps {
  lambdaSecurityGroupName: string;
  vpcProps: VpcLookupOptions;
  mainBusName: string;
  apiGatewayCognitoProps: OrcaBusApiGatewayProps;
}

export class WorkflowManagerStack extends Stack {
  private props: WorkflowManagerStackProps;
  private baseLayer: PythonLayerVersion;
  private readonly lambdaEnv;
  private readonly lambdaRuntimePythonVersion: aws_lambda.Runtime = aws_lambda.Runtime.PYTHON_3_12;
  private readonly lambdaRole: Role;
  private readonly lambdaSG: ISecurityGroup;
  private readonly mainBus: IEventBus;
  private readonly vpc: IVpc;

  private readonly WORKFLOW_MANAGER_DB_NAME = 'workflow_manager';
  private readonly WORKFLOW_MANAGER_DB_USER = 'workflow_manager';

  constructor(scope: Construct, id: string, props: WorkflowManagerStackProps) {
    super(scope, id, props);

    this.props = props;

    this.mainBus = EventBus.fromEventBusName(this, 'OrcaBusMain', props.mainBusName);
    this.vpc = Vpc.fromLookup(this, 'MainVpc', props.vpcProps);
    this.lambdaSG = SecurityGroup.fromLookupByName(
      this,
      'LambdaSecurityGroup',
      props.lambdaSecurityGroupName,
      this.vpc
    );

    // Create the registry and publish the schemas
    new WorkflowManagerSchemaRegistry(this, 'WorkflowManagerSchemaRegistry');

    this.lambdaRole = new Role(this, 'LambdaRole', {
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
      description: 'Lambda execution role for ' + id,
    });
    // FIXME it is best practise to such that we do not use AWS managed policy
    //  we should improve this at some point down the track.
    //  See https://github.com/umccr/orcabus/issues/174
    this.lambdaRole.addManagedPolicy(
      ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
    );
    this.lambdaRole.addManagedPolicy(
      ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole')
    );
    this.lambdaRole.addManagedPolicy(
      ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMReadOnlyAccess')
    );

    // Grab the database cluster
    const clusterResourceIdentifier = StringParameter.valueForStringParameter(
      this,
      DB_CLUSTER_RESOURCE_ID_PARAMETER_NAME
    );
    const clusterHostEndpoint = StringParameter.valueForStringParameter(
      this,
      DB_CLUSTER_ENDPOINT_HOST_PARAMETER_NAME
    );
    const dbCluster = DatabaseCluster.fromDatabaseClusterAttributes(this, 'OrcabusDbCluster', {
      clusterIdentifier: DB_CLUSTER_IDENTIFIER,
      clusterResourceIdentifier: clusterResourceIdentifier,
    });
    dbCluster.grantConnect(this.lambdaRole, this.WORKFLOW_MANAGER_DB_USER);

    this.lambdaEnv = {
      DJANGO_SETTINGS_MODULE: 'workflow_manager.settings.aws',
      EVENT_BUS_NAME: this.mainBus.eventBusName,
      PG_HOST: clusterHostEndpoint,
      PG_USER: this.WORKFLOW_MANAGER_DB_USER,
      PG_DB_NAME: this.WORKFLOW_MANAGER_DB_NAME,
    };

    this.baseLayer = new PythonLayerVersion(this, 'BaseLayer', {
      entry: path.join(__dirname, '../../app/deps'),
      compatibleRuntimes: [this.lambdaRuntimePythonVersion],
      compatibleArchitectures: [Architecture.ARM_64],
    });

    this.createMigrationHandler();
    this.createApiHandlerAndIntegration(props);
    this.createLegacyWrscEventHandler();
    this.createWruEventHandler();
    this.createAruEventHandler();
  }

  private createPythonFunction(name: string, props: object): PythonFunction {
    return new PythonFunction(this, name, {
      entry: path.join(__dirname, '../../app/'),
      runtime: this.lambdaRuntimePythonVersion,
      layers: [this.baseLayer],
      environment: this.lambdaEnv,
      securityGroups: [this.lambdaSG],
      vpc: this.vpc,
      vpcSubnets: { subnets: this.vpc.privateSubnets },
      role: this.lambdaRole,
      architecture: Architecture.ARM_64,
      memorySize: 1024,
      ...props,
    });
  }

  private createMigrationHandler() {
    this.createPythonFunction('Migration', {
      index: 'migrate.py',
      handler: 'handler',
      timeout: Duration.minutes(2),
    });
  }

  private createApiHandlerAndIntegration(props: WorkflowManagerStackProps) {
    const API_VERSION = 'v1';
    const apiFn: PythonFunction = this.createPythonFunction('Api', {
      index: 'api.py',
      handler: 'handler',
      timeout: Duration.seconds(28),
    });

    const wfmApi = new OrcaBusApiGateway(this, 'ApiGateway', props.apiGatewayCognitoProps);
    const httpApi = wfmApi.httpApi;

    const apiIntegration = new HttpLambdaIntegration('ApiIntegration', apiFn);

    // Routes for API schemas
    new HttpRoute(this, 'GetSchemaHttpRoute', {
      httpApi: wfmApi.httpApi,
      integration: apiIntegration,
      authorizer: new HttpNoneAuthorizer(), // No auth needed for schema
      routeKey: HttpRouteKey.with(`/schema/{PROXY+}`, HttpMethod.GET),
    });

    new HttpRoute(this, 'GetHttpRoute', {
      httpApi: httpApi,
      integration: apiIntegration,
      routeKey: HttpRouteKey.with('/{proxy+}', HttpMethod.GET),
    });

    new HttpRoute(this, 'PostHttpRoute', {
      httpApi: httpApi,
      integration: apiIntegration,
      routeKey: HttpRouteKey.with('/{proxy+}', HttpMethod.POST),
    });

    new HttpRoute(this, 'PatchHttpRoute', {
      httpApi: httpApi,
      integration: apiIntegration,
      routeKey: HttpRouteKey.with('/{proxy+}', HttpMethod.PATCH),
    });

    new HttpRoute(this, 'DeleteHttpRoute', {
      httpApi: httpApi,
      integration: apiIntegration,
      routeKey: HttpRouteKey.with('/{proxy+}', HttpMethod.DELETE),
    });

    // Route and permission for rerun cases where it needs to put event to mainBus
    this.mainBus.grantPutEventsTo(apiFn);
    new HttpRoute(this, 'PostRerunHttpRoute', {
      httpApi: httpApi,
      integration: apiIntegration,
      authorizer: wfmApi.authStackHttpLambdaAuthorizer,
      routeKey: HttpRouteKey.with(
        `/api/${API_VERSION}/workflowrun/{orcabusId}/rerun/{proxy+}`,
        HttpMethod.POST
      ),
    });
  }

  private createLegacyWrscEventHandler() {
    const procFn: PythonFunction = this.createPythonFunction('HandleWrscEventLegacy', {
      index: 'workflow_manager_proc/lambdas/handle_wrsc_event_legacy.py',
      handler: 'handler',
      timeout: Duration.seconds(28),
    });

    this.mainBus.grantPutEventsTo(procFn);

    const eventRule = new Rule(this, 'EventRule', {
      description: 'Rule to send WorkflowRunStateChange events to the HandleWrscEventLegacy Lambda',
      eventBus: this.mainBus,
    });

    eventRule.addTarget(new aws_events_targets.LambdaFunction(procFn));
    eventRule.addEventPattern({
      // See https://github.com/aws/aws-cdk/issues/30220
      // @ts-expect-error AWS CDK types don't support 'anything-but' pattern
      source: [{ 'anything-but': 'orcabus.workflowmanager' }],
      detailType: ['WorkflowRunStateChange'],
      detail: {
        workflowName: [{ exists: true }],
        workflowVersion: [{ exists: true }],
      },
    });
  }

  private createWruEventHandler() {
    const procFn: PythonFunction = this.createPythonFunction('HandleWruEvent', {
      index: 'workflow_manager_proc/lambdas/handle_wru_event.py',
      handler: 'handler',
      timeout: Duration.seconds(28),
    });

    this.mainBus.grantPutEventsTo(procFn);

    const eventRule = new Rule(this, 'EventRule2', {
      description: 'Rule to send WorkflowRunUpdate events to the HandleWruEvent Lambda',
      eventBus: this.mainBus,
    });

    eventRule.addTarget(new aws_events_targets.LambdaFunction(procFn));
    eventRule.addEventPattern({
      // See https://github.com/aws/aws-cdk/issues/30220
      // @ts-expect-error AWS CDK types don't support 'anything-but' pattern
      source: [{ 'anything-but': 'orcabus.workflowmanager' }],
      detailType: ['WorkflowRunUpdate'],
    });
  }

  private createAruEventHandler() {
    const procFn: PythonFunction = this.createPythonFunction('HandleAruEvent', {
      index: 'workflow_manager_proc/lambdas/handle_aru_event.py',
      handler: 'handler',
      timeout: Duration.seconds(28),
    });

    this.mainBus.grantPutEventsTo(procFn);

    const eventRule = new Rule(this, 'EventRuleARU', {
      description: 'Rule to send AnalysisRunUpdate events to the HandleAruEvent Lambda',
      eventBus: this.mainBus,
    });

    eventRule.addTarget(new aws_events_targets.LambdaFunction(procFn));
    eventRule.addEventPattern({
      // See https://github.com/aws/aws-cdk/issues/30220
      // @ts-expect-error AWS CDK types don't support 'anything-but' pattern
      source: [{ 'anything-but': 'orcabus.workflowmanager' }],
      detailType: ['AnalysisRunUpdate'],
    });
  }
}
