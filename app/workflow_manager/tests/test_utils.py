import time
from datetime import datetime, timedelta
from typing import List

from django.test import TestCase
from django.utils.timezone import make_aware

from workflow_manager.models import WorkflowRun, State, Payload
from workflow_manager.models.utils import WorkflowRunUtil, StateUtil, create_portal_run_id

from workflow_manager.viewsets.utils import parse_version, version_sort_key, compare_versions
from workflow_manager.tests.factories import WorkflowRunFactory, PayloadFactory


class VersionUtilsTests(TestCase):
    """Tests for workflow version parsing and comparison."""

    def test_parse_version_valid(self):
        """Valid XX.XX.XX format parses correctly."""
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("4.2.4"), (4, 2, 4))
        self.assertEqual(parse_version("0.6.0"), (0, 6, 0))

    def test_parse_version_invalid(self):
        """Non-conforming formats return None."""
        self.assertIsNone(parse_version("4-2-4--v2"))
        self.assertIsNone(parse_version("4-4-4"))
        self.assertIsNone(parse_version("2.1"))
        self.assertIsNone(parse_version(""))

    def test_version_sort_key(self):
        """Valid versions get tuple key; invalid get (0,0,0)."""
        self.assertEqual(version_sort_key("2.3.1"), (2, 3, 1))
        self.assertEqual(version_sort_key("4-2-4"), (0, 0, 0))

    def test_compare_versions(self):
        """Version comparison returns correct sign."""
        self.assertGreater(compare_versions("2.1.0", "2.0.0"), 0)
        self.assertLess(compare_versions("1.1.0", "2.0.0"), 0)
        self.assertEqual(compare_versions("0.7.0", "0.7.0"), 0)
        # Invalid formats sort lowest
        self.assertGreater(compare_versions("1.0.0", "4-2-4"), 0)


class UtilsTests(TestCase):

    def test_create_portal_run_id(self):
        """
        python manage.py test workflow_manager.tests.test_utils.UtilsTests.test_create_portal_run_id
        """
        portal_run_id_1 = create_portal_run_id()

        # making sure portal_run_id is different generated in different time
        time.sleep(1)
        portal_run_id_2 = create_portal_run_id()

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


class StateUtilTests(TestCase):
    """
    python manage.py test workflow_manager.tests.test_utils.StateUtilTests
    """

    def test_create_state_hash_identical(self):
        # two distinct objects with the same fields must yield the same hash
        s1 = State(status="READY", comment="foo")
        s2 = State(status="READY", comment="foo")
        h1 = StateUtil.create_state_hash(s1)
        h2 = StateUtil.create_state_hash(s2)
        self.assertEqual(h1, h2)

    def test_create_state_hash_different(self):
        # changing any of the relevant fields should change the hash
        s1 = State(status="READY", comment="foo")
        s2 = State(status="READY", comment="bar")
        self.assertNotEqual(
            StateUtil.create_state_hash(s1),
            StateUtil.create_state_hash(s2),
        )

    def test_create_state_hash_payload_and_none_handling(self):
        # payload payload_ref_id is taken into account; None values are ignored
        mock_payload1 = PayloadFactory(payload_ref_id="abc")
        mock_payload2 = PayloadFactory(payload_ref_id="def")

        base = State(status="DRAFT", comment=None, payload=None)
        # should complete without error and be reproducible
        base_hash = StateUtil.create_state_hash(base)
        self.assertIsInstance(base_hash, str)
        self.assertEqual(base_hash, StateUtil.create_state_hash(base))

        with_payload1 = State(
            status="DRAFT",
            comment=None,
            payload=mock_payload1,
        )
        with_payload1_dup = State(
            status="DRAFT",
            comment=None,
            payload=mock_payload1,
        )
        self.assertEqual(
            StateUtil.create_state_hash(with_payload1),
            StateUtil.create_state_hash(with_payload1_dup),
        )

        with_payload2 = State(
            status="DRAFT",
            comment=None,
            payload=mock_payload2,
        )
        self.assertNotEqual(
            StateUtil.create_state_hash(with_payload1),
            StateUtil.create_state_hash(with_payload2),
        )

    def test_create_state_hash_order(self):
        # the hash takes field names into account, not just values
        s1 = State(status="Z", comment="A")
        s2 = State(status="A", comment="Z")
        self.assertNotEqual(
            StateUtil.create_state_hash(s1),
            StateUtil.create_state_hash(s2),
        )
