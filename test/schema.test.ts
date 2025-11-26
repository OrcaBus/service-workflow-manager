import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { WorkflowManagerSchemaRegistry } from '../infrastructure/stage/schema';

let stack: cdk.Stack;

beforeEach(() => {
  stack = new cdk.Stack();
});

test('Test orcabus.workflowmanager WorkflowManagerSchemaRegistry Creation', () => {
  // pnpm test --- test/schema.test.ts

  new WorkflowManagerSchemaRegistry(stack, 'TestWorkflowManagerSchemaRegistry');
  const template = Template.fromStack(stack);

  console.log(template.toJSON());

  template.hasResourceProperties('AWS::EventSchemas::Schema', {
    SchemaName: 'orcabus.workflowmanager@WorkflowRunStateChange',
  });

  template.hasResourceProperties('AWS::EventSchemas::Schema', {
    SchemaName: 'orcabus.workflowmanager@WorkflowRunUpdate',
  });

  template.hasResourceProperties('AWS::EventSchemas::Schema', {
    SchemaName: 'orcabus.workflowmanager@AnalysisRunStateChange',
  });

  template.hasResourceProperties('AWS::EventSchemas::Schema', {
    SchemaName: 'orcabus.workflowmanager@AnalysisRunUpdate',
  });
});
