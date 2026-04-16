import uuid
from datetime import datetime

import ulid
from django.test import TestCase
from django.utils.timezone import make_aware

from workflow_manager.models import AnalysisRun, AnalysisRunState, State, Workflow
from workflow_manager.tests.factories import WorkflowRunFactory
from workflow_manager.tests.fixtures.sim_workflow import TestData
from workflow_manager.urls.base import api_base


class StatsViewSetTestCase(TestCase):
    base_endpoint = f"/{api_base}stats"

    def setUp(self):
        TestData().create_primary()
        self.wf = Workflow.objects.first()
        self.wfr_empty = WorkflowRunFactory(
            workflow=self.wf,
            workflow_run_name="EmptyWorkflowRunForStats",
            portal_run_id="8888",
        )

    def test_workflow_run_status_counts_returns_200(self):
        response = self.client.get(f"{self.base_endpoint}/workflow_run/status_counts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            set(data.keys()),
            {"all", "succeeded", "aborted", "failed", "resolved", "deprecated", "ongoing"},
        )
        self.assertGreaterEqual(data["all"], 1)

    def test_workflow_run_status_counts_not_inflated_by_same_timestamp_states(self):
        """Two State rows at the same timestamp must count as one run (tie-break by PK)."""
        before = self.client.get(f"{self.base_endpoint}/workflow_run/status_counts/").json()

        ts = make_aware(datetime(2024, 6, 15, 10, 0, 0))
        id_lo, id_hi = ulid.new().str, ulid.new().str
        if id_lo > id_hi:
            id_lo, id_hi = id_hi, id_lo
        while id_lo >= id_hi:
            id_hi = ulid.new().str

        wfr = WorkflowRunFactory(
            workflow=self.wf,
            portal_run_id=f"tie-{uuid.uuid4().hex[:24]}",
            workflow_run_name="Same timestamp states",
        )
        State.objects.create(
            orcabus_id=f"stt.{id_lo}",
            status="FAILED",
            timestamp=ts,
            workflow_run=wfr,
        )
        State.objects.create(
            orcabus_id=f"stt.{id_hi}",
            status="SUCCEEDED",
            timestamp=ts,
            workflow_run=wfr,
        )

        after = self.client.get(f"{self.base_endpoint}/workflow_run/status_counts/").json()

        self.assertEqual(after["all"], before["all"] + 1)
        self.assertEqual(after["succeeded"], before["succeeded"] + 1)
        self.assertEqual(after["failed"], before["failed"])

    def test_analysis_run_status_counts_not_inflated_by_same_timestamp_states(self):
        """Two AnalysisRunState rows at the same timestamp must count as one run."""
        before = self.client.get(f"{self.base_endpoint}/analysis_run/status_counts/").json()

        ts = make_aware(datetime(2024, 6, 15, 11, 0, 0))
        id_lo, id_hi = ulid.new().str, ulid.new().str
        if id_lo > id_hi:
            id_lo, id_hi = id_hi, id_lo
        while id_lo >= id_hi:
            id_hi = ulid.new().str

        anr = AnalysisRun.objects.create(
            orcabus_id=f"anr.{ulid.new().str}",
            analysis_run_name="Same timestamp ar states",
        )
        AnalysisRunState.objects.create(
            orcabus_id=f"ars.{id_lo}",
            status="FAILED",
            timestamp=ts,
            analysis_run=anr,
        )
        AnalysisRunState.objects.create(
            orcabus_id=f"ars.{id_hi}",
            status="SUCCEEDED",
            timestamp=ts,
            analysis_run=anr,
        )

        after = self.client.get(f"{self.base_endpoint}/analysis_run/status_counts/").json()

        self.assertEqual(after["all"], before["all"] + 1)
        self.assertEqual(after["succeeded"], before["succeeded"] + 1)
        self.assertEqual(after["failed"], before["failed"])

    def test_analysis_run_status_counts_returns_200(self):
        response = self.client.get(f"{self.base_endpoint}/analysis_run/status_counts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            set(data.keys()),
            {"all", "succeeded", "aborted", "failed", "resolved", "deprecated", "ongoing"},
        )

    def test_workflow_status_counts_returns_200(self):
        response = self.client.get(f"{self.base_endpoint}/workflow/status_counts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("all", data)
        self.assertIn("unvalidated", data)
        self.assertIn("validated", data)
        self.assertIn("deprecated", data)
        self.assertIn("failed", data)
        self.assertGreaterEqual(data["all"], 1)

    def test_analysis_status_counts_returns_200(self):
        response = self.client.get(f"{self.base_endpoint}/analysis/status_counts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("all", data)
        self.assertIn("active", data)
        self.assertIn("inactive", data)

    def test_grouped_workflow_status_counts_returns_200(self):
        response = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            set(data.keys()),
            {"all", "unvalidated", "validated", "deprecated", "failed"},
        )
        self.assertGreaterEqual(data["all"], 1)

    def test_grouped_workflow_status_counts_only_latest_version_per_name(self):
        from workflow_manager.models.workflow import ExecutionEngine, ValidationState

        name = f"wfm_stats_group_{uuid.uuid4().hex[:16]}"
        before = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/").json()

        Workflow.objects.create(
            name=name,
            version="1.0.0",
            code_version="dup-a",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.UNVALIDATED,
        )
        Workflow.objects.create(
            name=name,
            version="10.0.0",
            code_version="dup-b",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )

        after = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/").json()

        self.assertEqual(after["all"], before["all"] + 1)
        self.assertEqual(after["validated"], before["validated"] + 1)
        self.assertEqual(after["unvalidated"], before["unvalidated"])

    def test_grouped_workflow_status_counts_semver_order_not_creation_order(self):
        """Latest-per-name must be determined by semver, not by creation (ULID) order.

        Creating v0.6.1 *after* v0.7.0 should still pick v0.7.0 as the latest.
        """
        from workflow_manager.models.workflow import ExecutionEngine, ValidationState

        name = f"wfm_stats_semver_{uuid.uuid4().hex[:16]}"
        before = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/").json()

        # Created first → lower ULID
        Workflow.objects.create(
            name=name,
            version="0.7.0",
            code_version="a",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )
        # Created second → higher ULID, but *lower* semver
        Workflow.objects.create(
            name=name,
            version="0.6.1",
            code_version="b",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.UNVALIDATED,
        )

        after = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/").json()

        # v0.7.0 (VALIDATED) should be picked, not v0.6.1 (UNVALIDATED)
        self.assertEqual(after["all"], before["all"] + 1)
        self.assertEqual(after["validated"], before["validated"] + 1)
        self.assertEqual(after["unvalidated"], before["unvalidated"])

    def test_grouped_workflow_status_counts_case_insensitive_grouping(self):
        """Workflows with the same name in different cases should merge into one group."""
        from workflow_manager.models.workflow import ExecutionEngine, ValidationState

        base_name = f"wfm_case_{uuid.uuid4().hex[:16]}"
        before = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/").json()

        Workflow.objects.create(
            name=base_name.upper(),
            version="0.5.0",
            code_version="a",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.UNVALIDATED,
        )
        Workflow.objects.create(
            name=base_name.lower(),
            version="1.0.0",
            code_version="b",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )
        Workflow.objects.create(
            name=base_name.capitalize(),
            version="0.8.0",
            code_version="c",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.DEPRECATED,
        )

        after = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/").json()

        # All three case variants should merge into one group; latest is v1.0.0 (VALIDATED)
        self.assertEqual(after["all"], before["all"] + 1)
        self.assertEqual(after["validated"], before["validated"] + 1)
        self.assertEqual(after["unvalidated"], before["unvalidated"])
        self.assertEqual(after["deprecated"], before["deprecated"])

    def test_grouped_workflow_status_counts_non_semver_version(self):
        """Non-semver versions (e.g. containing hyphens) must not crash the CAST."""
        from workflow_manager.models.workflow import ExecutionEngine, ValidationState

        name = f"wfm_nonsemver_{uuid.uuid4().hex[:16]}"
        before = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/").json()

        # Non-semver version that would cause CAST errors if not guarded
        Workflow.objects.create(
            name=name,
            version="1--1.2.3",
            code_version="a",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.UNVALIDATED,
        )
        # Valid semver - should be selected as latest (non-semver falls back to (0,0,0))
        Workflow.objects.create(
            name=name,
            version="0.1.0",
            code_version="b",
            execution_engine=ExecutionEngine.ICA,
            validation_state=ValidationState.VALIDATED,
        )

        after = self.client.get(f"{self.base_endpoint}/grouped_workflow/status_counts/").json()

        # v0.1.0 (VALIDATED) beats "1--1.2.3" (treated as (0,0,0))
        self.assertEqual(after["all"], before["all"] + 1)
        self.assertEqual(after["validated"], before["validated"] + 1)
        self.assertEqual(after["unvalidated"], before["unvalidated"])
