# Generated manually for Comment.severity (see issue #144)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflow_manager", "0021_comment_analysis_run_alter_comment_workflow_run"),
    ]

    operations = [
        migrations.AddField(
            model_name="comment",
            name="severity",
            field=models.CharField(
                choices=[
                    ("DEBUG", "Debug"),
                    ("INFO", "Info"),
                    ("WARNING", "Warning"),
                    ("ERROR", "Error"),
                ],
                default="INFO",
                max_length=16,
            ),
        ),
    ]
