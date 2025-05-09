# Generated by Django 5.1.2 on 2024-12-17 08:04

import workflow_manager.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('workflow_manager', '0002_workflowruncomment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='analysis',
            name='orcabus_id',
            field=workflow_manager.fields.OrcaBusIdField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='analysiscontext',
            name='orcabus_id',
            field=workflow_manager.fields.OrcaBusIdField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='analysisrun',
            name='orcabus_id',
            field=workflow_manager.fields.OrcaBusIdField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='library',
            name='orcabus_id',
            field=workflow_manager.fields.OrcaBusIdField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='libraryassociation',
            name='orcabus_id',
            field=workflow_manager.fields.OrcaBusIdField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='payload',
            name='orcabus_id',
            field=workflow_manager.fields.OrcaBusIdField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='state',
            name='orcabus_id',
            field=workflow_manager.fields.OrcaBusIdField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='orcabus_id',
            field=workflow_manager.fields.OrcaBusIdField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='workflowrun',
            name='orcabus_id',
            field=workflow_manager.fields.OrcaBusIdField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='workflowruncomment',
            name='orcabus_id',
            field=workflow_manager.fields.OrcaBusIdField(primary_key=True, serialize=False),
        ),
    ]
