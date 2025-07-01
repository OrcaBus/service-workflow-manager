from django.core.management import BaseCommand

from workflow_manager.tests.fixtures.sim_analysis import TestData


class Command(BaseCommand):
    help = """
        Generate mock data and populate DB for local testing.
        python manage.py generate_mock_analysis_run
    """

    def handle(self, *args, **options):

        TestData() \
            .assign_analysis() \
            .prep_workflow_runs()

        print("Done")
