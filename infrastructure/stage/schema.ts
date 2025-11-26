import { Construct } from 'constructs';
import { aws_eventschemas } from 'aws-cdk-lib';
import { readFileSync } from 'fs';
import path from 'path';
import { EVENT_SCHEMA_REGISTRY_NAME } from '@orcabus/platform-cdk-constructs/shared-config/event-bridge';

export interface SchemaProps {
  schemaName: string;
  schemaDescription: string;
  schemaLocation: string;
}

export class WorkflowManagerSchemaRegistry extends Construct {
  private readonly SCHEMA_TYPE = 'JSONSchemaDraft4';

  constructor(scope: Construct, id: string) {
    super(scope, id);

    // Publish schema into the registry
    getSchemas().forEach((s) => {
      new aws_eventschemas.CfnSchema(this, s.schemaName, {
        content: readFileSync(s.schemaLocation, 'utf-8'),
        type: this.SCHEMA_TYPE,
        registryName: EVENT_SCHEMA_REGISTRY_NAME,
        description: s.schemaDescription,
        schemaName: s.schemaName,
      });
    });
  }
}

export const getSchemas = (): Array<SchemaProps> => {
  const docBase: string = '../../docs/events';

  // Add a new schema to the list
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
