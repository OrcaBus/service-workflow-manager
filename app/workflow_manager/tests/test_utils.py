import time
from datetime import datetime, timedelta
from typing import List

from django.test import TestCase
from django.utils.timezone import make_aware

from workflow_manager.models import WorkflowRun, State, WorkflowRunUtil, utils
from workflow_manager.tests.factories import WorkflowRunFactory


class UtilsTests(TestCase):

    def test_create_portal_run_id(self):
        """
        python manage.py test workflow_manager.tests.test_utils.UtilsTests.test_create_portal_run_id
        """
        portal_run_id_1 = utils.create_portal_run_id()

        # making sure portal_run_id is different generated in different time
        time.sleep(1)
        portal_run_id_2 = utils.create_portal_run_id()

        self.assertIsNotNone(portal_run_id_1)
        self.assertEqual(len(portal_run_id_1), 16)
        self.assertNotEqual(portal_run_id_1, portal_run_id_2)


class WorkflowRunUtilUnitTests(TestCase):
    """TODO add more unit tests to cover WorkflowRunUtil impls"""

    def test_get_last_state(self):
        """
        python manage.py test workflow_manager.tests.test_utils.WorkflowRunUtilUnitTests.test_get_last_state
        """
        _ = WorkflowRunFactory()

        wfr: WorkflowRun = WorkflowRun.objects.first()
        s1: State = State(
            timestamp=make_aware(datetime(2024, 1, 3, 23, 55, 59, 342380)),
            workflow_run=wfr,
            status='DRAFT'
        )
        s2: State = State(
            timestamp=make_aware(datetime(2024, 1, 1, 23, 55, 59, 342380)),
            workflow_run=wfr,
            status='DRAFT'
        )
        s3: State = State(
            timestamp=make_aware(datetime(2024, 1, 4, 23, 55, 59, 342380)),
            workflow_run=wfr,
            status='DRAFT'
        )
        s4: State = State(
            timestamp=make_aware(datetime(2024, 1, 2, 23, 55, 59, 342380)),
            workflow_run=wfr,
            status='DRAFT'
        )

        # Test different orders, they all have to come to the same conclusion
        states: List[State] = [s1, s2, s3, s4]
        latest: State = WorkflowRunUtil.get_latest_state(states)
        self.assertEqual(s3.timestamp, latest.timestamp)

        states: List[State] = [s4, s1, s2, s3]
        latest: State = WorkflowRunUtil.get_latest_state(states)
        self.assertEqual(s3.timestamp, latest.timestamp)

        states: List[State] = [s3, s2, s1, s4]
        latest: State = WorkflowRunUtil.get_latest_state(states)
        self.assertEqual(s3.timestamp, latest.timestamp)

        # Now test from WorkflowRun level (need to persist DB objects though)
        s1.save()
        s2.save()
        s3.save()
        s4.save()
        wfr.save()
        util = WorkflowRunUtil(wfr)
        latest = util.get_current_state()
        self.assertEqual(s3.timestamp, latest.timestamp)

        # Test we can correctly apply a time delta
        t1 = s1.timestamp
        t2 = s2.timestamp
        delta = t1 - t2  # = 2 days
        window = timedelta(hours=1)
        self.assertTrue(delta > window, "delta > 1h")
