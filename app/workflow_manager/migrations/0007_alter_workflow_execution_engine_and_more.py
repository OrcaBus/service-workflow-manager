# Generated by Django 5.2.4 on 2025-07-24 01:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "workflow_manager",
            "0006_alter_analysis_description_alter_analysis_status_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="workflow",
            name="execution_engine",
            field=models.CharField(
                choices=[
                    ("Unknown", "Unknown"),
                    ("ICA", "Ica"),
                    ("AWS_BATCH", "Aws Batch"),
                    ("AWS_ECS", "Aws Ecs"),
                ],
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="workflow",
            name="execution_engine_pipeline_id",
            field=models.CharField(default="Unknown", max_length=255),
        ),
    ]
