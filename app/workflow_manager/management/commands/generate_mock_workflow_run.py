from django.core.management import BaseCommand

from workflow_manager.models import Workflow
from workflow_manager.tests.fixtures.sim_workflow import TestData


# https://docs.djangoproject.com/en/5.0/howto/custom-management-commands/
class Command(BaseCommand):
    help = """
        Generate mock data and populate DB for local testing.
    """

    def handle(self, *args, **options):
        # don't do anything if there is already mock data
        if Workflow.objects.filter(name__startswith=TestData.WORKFLOW_NAME).exists():
            print("Mock data found, Skipping creation.")
            return

        # First case: a primary workflow with two executions linked to 4 libraries
        # The first execution failed and led to a repetition that succeeded
        TestData() \
            .create_primary() \
            .create_secondary()

        print("Done")
