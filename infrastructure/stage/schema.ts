import { Construct } from 'constructs';
import { aws_eventschemas } from 'aws-cdk-lib';
import { readFileSync } from 'fs';
import path from 'path';

export interface SchemaProps {
  schemaName: string;
  schemaDescription: string;
  schemaLocation: string;
}

export class WorkflowManagerSchemaRegistry extends Construct {
  private readonly SCHEMA_REGISTRY_NAME = 'orcabus.workflowmanager';
  private readonly SCHEMA_TYPE = 'JSONSchemaDraft4';

  constructor(scope: Construct, id: string) {
    super(scope, id);

    // Create EventBridge schema registry
    const registry = new aws_eventschemas.CfnRegistry(this, this.SCHEMA_REGISTRY_NAME, {
      registryName: this.SCHEMA_REGISTRY_NAME,
      description: 'Schema Registry for ' + this.SCHEMA_REGISTRY_NAME,
    });

    // Publish schema into the registry
    getSchemas().forEach((s) => {
      const schema = new aws_eventschemas.CfnSchema(this, s.schemaName, {
        content: readFileSync(s.schemaLocation, 'utf-8'),
        type: this.SCHEMA_TYPE,
        registryName: s.schemaName,
        description: s.schemaDescription,
        schemaName: s.schemaName,
      });

      // Make Schema component depends on the Registry component
      // Essentially, it forms the deployment dependency at CloudFormation
      schema.addDependency(registry);
    });
  }
}

export const getSchemas = (): Array<SchemaProps> => {
  const docBase: string = '../../docs/events';

  // Add new schema to the list
  return [
    {
      schemaName: 'orcabus.workflowmanager@WorkflowRunStateChange',
      schemaDescription: 'State change event for workflow run by WorkflowManager',
      schemaLocation: path.join(
        __dirname,
        docBase + '/WorkflowRunStateChange/WorkflowRunStateChange.schema.json'
      ),
    },
    {
      schemaName: 'orcabus.workflowmanager@WorkflowRunUpdate',
      schemaDescription: 'Update event for workflow run by external service',
      schemaLocation: path.join(
        __dirname,
        docBase + '/WorkflowRunUpdate/WorkflowRunUpdate.schema.json'
      ),
    },
    {
      schemaName: 'orcabus.workflowmanager@AnalysisRunStateChange',
      schemaDescription: 'State change event for analysis run by WorkflowManager',
      schemaLocation: path.join(
        __dirname,
        docBase + '/AnalysisRunStateChange/AnalysisRunStateChange.schema.json'
      ),
    },
    {
      schemaName: 'orcabus.workflowmanager@AnalysisRunUpdate',
      schemaDescription: 'Update event for analysis run by external service',
      schemaLocation: path.join(
        __dirname,
        docBase + '/AnalysisRunUpdate/AnalysisRunUpdate.schema.json'
      ),
    },
  ];
};
