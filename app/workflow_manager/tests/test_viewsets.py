import logging
import os
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils.timezone import make_aware
from libumccr.aws import libeb

from workflow_manager.models import Comment, WorkflowRun, LibraryAssociation, Payload, Workflow
from workflow_manager.viewsets.workflow_run import WorkflowRunViewSet, _build_keyword_params
from workflow_manager.tests.factories import WorkflowRunFactory, StateFactory, WorkflowFactory
from workflow_manager.tests.fixtures.sim_workflow import TestData
from workflow_manager.urls.base import api_base

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class WorkflowViewSetTestCase(TestCase):
    endpoint = f"/{api_base}workflow"

    def setUp(self):
        WorkflowFactory.create_batch(size=1)

    def test_get_api(self):
        """
        python manage.py test workflow_manager.tests.test_viewsets.WorkflowViewSetTestCase.test_get_api
        """
        response = self.client.get(f"{self.endpoint}/")
        logger.info(response.content)
        self.assertEqual(response.status_code, 200, 'Ok status response is expected')

    def test_list_groups_by_name_returns_highest_version_with_history(self):
        """
        Grouped API groups workflows by name, returns only highest version, includes history.
        python manage.py test workflow_manager.tests.test_viewsets.WorkflowViewSetTestCase.test_list_groups_by_name_returns_highest_version_with_history
        """
        from workflow_manager.models.workflow import ExecutionEngine, ValidationState

        # Create workflows with same name, different versions (need unique code_version for unique_together)
        Workflow.objects.create(
            name="sash", version="0.6.0", code_version="a",
            execution_engine=ExecutionEngine.ICA, validation_state=ValidationState.VALIDATED
        )
        Workflow.objects.create(
            name="sash", version="0.7.0", code_version="b",
            execution_engine=ExecutionEngine.ICA, validation_state=ValidationState.VALIDATED
        )
        Workflow.objects.create(
            name="sash", version="0.6.1", code_version="c",
            execution_engine=ExecutionEngine.ICA, validation_state=ValidationState.VALIDATED
        )
        Workflow.objects.create(
            name="other", version="1.0.0", code_version="d",
            execution_engine=ExecutionEngine.ICA, validation_state=ValidationState.VALIDATED
        )

        response = self.client.get(f"{self.endpoint}/grouped/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data.get("results", data) if "results" in data else data

        # Should return unique workflow names; sash group has highest 0.7.0
        names = [r["name"] for r in results]
        self.assertIn("sash", names)
        self.assertIn("other", names)

        sash_result = next(r for r in results if r["name"] == "sash")
        self.assertEqual(sash_result["version"], "0.7.0", "sash should return highest version")
        self.assertIn("history", sash_result)
        self.assertEqual(len(sash_result["history"]), 3, "sash history should have 3 version records")

    def test_list_groups_by_name_case_insensitive(self):
        """
        Workflow names are grouped case-insensitively (Sash, sash, SASH = same group).
        python manage.py test workflow_manager.tests.test_viewsets.WorkflowViewSetTestCase.test_list_groups_by_name_case_insensitive
        """
        from workflow_manager.models.workflow import ExecutionEngine, ValidationState

        Workflow.objects.create(
            name="Sash", version="0.6.0", code_version="a",
            execution_engine=ExecutionEngine.ICA, validation_state=ValidationState.VALIDATED
        )
        Workflow.objects.create(
            name="sash", version="0.7.0", code_version="b",
            execution_engine=ExecutionEngine.ICA, validation_state=ValidationState.VALIDATED
        )
        Workflow.objects.create(
            name="SASH", version="0.5.0", code_version="c",
            execution_engine=ExecutionEngine.ICA, validation_state=ValidationState.VALIDATED
        )

        response = self.client.get(f"{self.endpoint}/grouped/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data.get("results", data)

        sash_results = [r for r in results if r["name"].lower() == "sash"]
        self.assertEqual(len(sash_results), 1, "Sash/sash/SASH should merge into one group")
        self.assertEqual(sash_results[0]["version"], "0.7.0", "Highest version across case variants")
        self.assertEqual(len(sash_results[0]["history"]), 3, "History should include all 3 case variants")


class WorkflowRunRerunViewSetTestCase(TestCase):
    endpoint = f"/{api_base}workflowrun"

    def setUp(self):
        os.environ["EVENT_BUS_NAME"] = "mock-bus"

        # create primary test data from workflow fixtures
        TestData() \
            .create_primary()

        self._real_emit_event = libeb.emit_event
        libeb.emit_events = MagicMock()

    def tearDown(self) -> None:
        libeb.emit_event = self._real_emit_event

    def test_rerun_api(self):
        """
        python manage.py test workflow_manager.tests.test_viewsets.WorkflowRunRerunViewSetTestCase.test_rerun_api
        """
        wfl_run = WorkflowRun.objects.all().first()
        payload = wfl_run.states.get(status='READY').payload
        payload.data = {
            "inputs": {
                "someUri": "s3://random/prefix/",
                "dataset": "BRCA"
            },
            "engineParameters": {
                "sourceUri": f"s3://bucket/{wfl_run.portal_run_id}/",
            }
        }
        payload.save()

        response = self.client.post(f"{self.endpoint}/{wfl_run.orcabus_id}/rerun")
        self.assertIn(response.status_code, [400], 'Workflow name associated with the workflow run is not allowed')

        # Change the workflow name to 'rnasum' as this is the only allowed workflow name for rerun
        wfl = Workflow.objects.all().first()
        wfl.name = "rnasum"
        wfl.save()

        response = self.client.post(f"{self.endpoint}/{wfl_run.orcabus_id}/rerun", data={"dataset": "INVALID_CHOICE"})
        self.assertIn(response.status_code, [400], 'Invalid payload expected')

        response = self.client.post(f"{self.endpoint}/{wfl_run.orcabus_id}/rerun", data={"dataset": "PANCAN"})
        self.assertIn(response.status_code, [200], 'Expected a successful response')
        self.assertTrue(wfl_run.portal_run_id not in str(response.content), 'expect old portal_rub_id replaced')

        response = self.client.post(f"{self.endpoint}/{wfl_run.orcabus_id}/rerun", data={"dataset": "BRCA"})
        self.assertIn(response.status_code, [400], 'Rerun duplication with same input error expected')

        response = self.client.post(f"{self.endpoint}/{wfl_run.orcabus_id}/rerun",
                                    data={"dataset": "BRCA", "allow_duplication": True})
        self.assertIn(response.status_code, [200],
                      'Rerun with same input allowed when `allow_duplication` is set to True')

        # Unique Library Test - library IDs are treated as a unique set

        # Create a PANCAN payload with a library so the rerun starts from this workflow run
        wfr_new = WorkflowRunFactory(
            workflow_run_name="AdditionalTestWorkflowRun",
            portal_run_id="9876",
            workflow=wfl
        )
        new_payload = Payload.objects.create(
            version="1.0.0",
            payload_ref_id="01H6GZ8X4YJ5V9Q2F7A3B6CDE8",
            data={
                "inputs": {
                    "someUri": "s3://random/prefix/",
                    "dataset": "PANCAN"
                },
                "engineParameters": {
                    "sourceUri": f"s3://bucket/{wfr_new.portal_run_id}/",
                }
            }
        )
        for i, state in enumerate(["DRAFT", "READY", "RUNNING", "SUCCEEDED"]):
            StateFactory(
                workflow_run=wfr_new,
                status=state,
                payload=new_payload,
                timestamp=make_aware(datetime.now() + timedelta(hours=i))
            )
        LibraryAssociation.objects.create(
            workflow_run=wfr_new,
            library=wfl_run.libraries.all().first(),
            association_date=make_aware(datetime.now()),
            status="ACTIVE",
        )

        # The BCRA has been run in the initial payload (before the Unique Library Test)
        # This will trigger the rerun with different library set
        response = self.client.post(f"{self.endpoint}/{wfr_new.orcabus_id}/rerun", data={"dataset": "BRCA"})
        self.assertIn(response.status_code, [200],
                      'Rerun with the same input is allowed when using a different library set')


class WorkflowRunViewSetHelpersTestCase(TestCase):
    """Unit tests for WorkflowRunViewSet helper functions."""

    def test_build_keyword_params_excludes_custom_params(self):
        from django.http import QueryDict

        qd = QueryDict("start_time=2024-01-01&workflow__orcabus_id=wfl.123&search=foo")
        result = _build_keyword_params(qd)
        self.assertEqual(result, {"workflow__orcabus_id": ["wfl.123"]})

    def test_build_keyword_params_preserves_multiple_values(self):
        from django.http import QueryDict

        qd = QueryDict(mutable=True)
        qd.setlist("workflow__orcabus_id", ["wfl.1", "wfl.2"])
        result = _build_keyword_params(qd)
        self.assertEqual(result["workflow__orcabus_id"], ["wfl.1", "wfl.2"])

    def test_parse_datetime_safe_valid(self):
        result = WorkflowRunViewSet._parse_datetime_safe("2024-01-15T10:30:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

    def test_parse_datetime_safe_invalid_returns_none(self):
        self.assertIsNone(WorkflowRunViewSet._parse_datetime_safe("invalid"))
        self.assertIsNone(WorkflowRunViewSet._parse_datetime_safe(""))
        self.assertIsNone(WorkflowRunViewSet._parse_datetime_safe(None))
        self.assertIsNone(WorkflowRunViewSet._parse_datetime_safe(123))

    def test_validate_ordering_valid(self):
        self.assertEqual(WorkflowRunViewSet._validate_ordering("orcabus_id"), "orcabus_id")
        self.assertEqual(WorkflowRunViewSet._validate_ordering("-orcabus_id"), "-orcabus_id")
        self.assertEqual(WorkflowRunViewSet._validate_ordering("  orcabus_id  "), "orcabus_id")

    def test_validate_ordering_invalid_returns_default(self):
        self.assertEqual(WorkflowRunViewSet._validate_ordering(""), "-orcabus_id")
        self.assertEqual(WorkflowRunViewSet._validate_ordering("invalid_field"), "-orcabus_id")
        self.assertEqual(WorkflowRunViewSet._validate_ordering(None), "-orcabus_id")


class WorkflowRunViewSetTestCase(TestCase):
    """Tests for WorkflowRunViewSet list, filters, ongoing, and unresolved actions."""

    endpoint = f"/{api_base}workflowrun"

    def setUp(self):
        from workflow_manager.tests.fixtures.sim_workflow import TestData

        TestData().create_primary()

    def test_list_returns_200(self):
        response = self.client.get(f"{self.endpoint}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)
        self.assertGreater(len(data["results"]), 0)

    def test_list_with_start_time_and_end_time(self):
        from datetime import datetime, timedelta
        from django.utils.timezone import make_aware

        start = make_aware(datetime.now() + timedelta(hours=1))
        end = make_aware(datetime.now() + timedelta(hours=3))
        response = self.client.get(
            f"{self.endpoint}/",
            {"start_time": start.isoformat(), "end_time": end.isoformat()},
        )
        self.assertEqual(response.status_code, 200)

    def test_list_with_is_ongoing_true(self):
        response = self.client.get(f"{self.endpoint}/", {"is_ongoing": "true"})
        self.assertEqual(response.status_code, 200)

    def test_list_with_status_filter(self):
        response = self.client.get(f"{self.endpoint}/", {"status": "FAILED"})
        self.assertEqual(response.status_code, 200)

    def test_list_with_order_by_timestamp(self):
        response = self.client.get(f"{self.endpoint}/", {"order_by": "timestamp"})
        self.assertEqual(response.status_code, 200)

    def test_list_with_order_by_minus_timestamp(self):
        response = self.client.get(f"{self.endpoint}/", {"order_by": "-timestamp"})
        self.assertEqual(response.status_code, 200)

    def test_list_with_search(self):
        wfr = WorkflowRun.objects.first()
        response = self.client.get(
            f"{self.endpoint}/",
            {"search": wfr.workflow_run_name[:10] if wfr.workflow_run_name else "Test"},
        )
        self.assertEqual(response.status_code, 200)

    def test_list_with_keyword_params(self):
        wfr = WorkflowRun.objects.first()
        response = self.client.get(
            f"{self.endpoint}/",
            {"workflow__orcabus_id": wfr.workflow.orcabus_id},
        )
        self.assertEqual(response.status_code, 200)

    def test_ongoing_action_returns_200(self):
        response = self.client.get(f"{self.endpoint}/ongoing/")
        self.assertEqual(response.status_code, 200)

    def test_ongoing_with_ordering(self):
        response = self.client.get(
            f"{self.endpoint}/ongoing/",
            {"ordering": "orcabus_id"},
        )
        self.assertEqual(response.status_code, 200)

    def test_ongoing_with_keyword_and_status(self):
        wfr = WorkflowRun.objects.first()
        response = self.client.get(
            f"{self.endpoint}/ongoing/",
            {"workflow__orcabus_id": wfr.workflow.orcabus_id, "status": "RUNNING"},
        )
        self.assertEqual(response.status_code, 200)

    def test_unresolved_action_returns_200(self):
        response = self.client.get(f"{self.endpoint}/unresolved/")
        self.assertEqual(response.status_code, 200)

    def test_unresolved_with_ordering(self):
        response = self.client.get(
            f"{self.endpoint}/unresolved/",
            {"ordering": "-orcabus_id"},
        )
        self.assertEqual(response.status_code, 200)

    def test_retrieve_returns_200(self):
        wfr = WorkflowRun.objects.first()
        response = self.client.get(f"{self.endpoint}/{wfr.orcabus_id}/")
        self.assertEqual(response.status_code, 200)


class AnalysisRunViewSetTestCase(TestCase):
    """Tests for AnalysisRunViewSet list and retrieve."""

    endpoint = f"/{api_base}analysisrun"

    def setUp(self):
        from workflow_manager.tests.fixtures.sim_analysis import TestData

        TestData().assign_analysis()

    def test_list_returns_200(self):
        response = self.client.get(f"{self.endpoint}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)

    def test_list_with_keyword_params(self):
        from workflow_manager.models import AnalysisRun

        ar = AnalysisRun.objects.filter(analysis__isnull=False).first()
        if ar:
            response = self.client.get(
                f"{self.endpoint}/",
                {"analysis__orcabus_id": ar.analysis.orcabus_id},
            )
            self.assertEqual(response.status_code, 200)

    def test_retrieve_returns_200(self):
        from workflow_manager.models import AnalysisRun

        ar = AnalysisRun.objects.first()
        if ar:
            response = self.client.get(f"{self.endpoint}/{ar.orcabus_id}/")
            self.assertEqual(response.status_code, 200)


class CommentViewSetTestCase(TestCase):
    endpoint = f"/{api_base}workflowrun"

    def setUp(self):
        TestData().create_primary()
        self.wfr = WorkflowRun.objects.first()

    def test_list_comments_empty(self):
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_create_comment_success(self):
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/"
        response = self.client.post(
            url,
            data={"text": "New comment", "created_by": "tester"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["text"], "New comment")
        self.assertEqual(data.get("createdBy", data.get("created_by")), "tester")
        self.assertEqual(data.get("severity"), "INFO")

    def test_create_comment_with_optional_severity(self):
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/"
        response = self.client.post(
            url,
            data={
                "text": "Error comment",
                "created_by": "tester",
                "severity": "ERROR",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["text"], "Error comment")
        self.assertEqual(data.get("severity"), "ERROR")

    def test_create_comment_parent_not_found(self):
        url = f"{self.endpoint}/wfr.nonexistent123/comment/"
        response = self.client.post(
            url,
            data={"text": "x", "created_by": "u"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("WorkflowRun not found", response.json()["detail"])

    def test_create_comment_missing_required_fields(self):
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/"
        response = self.client.post(
            url,
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("createdBy and text fields are required", response.json()["detail"])

    def test_update_comment_success(self):
        c = Comment.objects.create(
            workflow_run=self.wfr, text="original", created_by="tester"
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"text": "updated", "created_by": "tester"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.text, "updated")

    def test_update_comment_permission_denied(self):
        c = Comment.objects.create(
            workflow_run=self.wfr, text="original", created_by="creator"
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"text": "hacked", "created_by": "other_user"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_update_comment_extra_fields_ignored(self):
        c = Comment.objects.create(
            workflow_run=self.wfr, text="original", created_by="tester"
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"text": "ok", "created_by": "tester", "extra_field": "x"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.text, "ok")

    def test_update_comment_severity_updated(self):
        c = Comment.objects.create(
            workflow_run=self.wfr,
            text="original",
            created_by="tester",
            severity="WARNING",
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={
                "text": "updated",
                "created_by": "tester",
                "severity": "ERROR",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.severity, "ERROR")
        self.assertEqual(c.text, "updated")

    def test_update_comment_severity_only(self):
        c = Comment.objects.create(
            workflow_run=self.wfr,
            text="unchanged",
            created_by="tester",
            severity="INFO",
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"severity": "WARNING", "created_by": "tester"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.severity, "WARNING")
        self.assertEqual(c.text, "unchanged")

    def test_update_comment_requires_text_or_severity(self):
        c = Comment.objects.create(
            workflow_run=self.wfr, text="x", created_by="tester"
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"created_by": "tester"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch(
        "workflow_manager.viewsets.base.decode_rs256_jwt_payload_without_verification",
        return_value={"email": "tester"},
    )
    def test_update_comment_uses_bearer_when_created_by_omitted(self, _mock_decode):
        c = Comment.objects.create(
            workflow_run=self.wfr, text="original", created_by="tester"
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"text": "via jwt"},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer fake.jwt.token",
        )
        self.assertEqual(response.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.text, "via jwt")

    def test_update_comment_requires_bearer_when_created_by_omitted(self):
        c = Comment.objects.create(
            workflow_run=self.wfr, text="original", created_by="tester"
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.patch(
            url,
            data={"text": "no auth"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @patch(
        "workflow_manager.viewsets.base.decode_rs256_jwt_payload_without_verification",
        return_value={"email": "tester"},
    )
    def test_soft_delete_success(self, _mock_decode):
        c = Comment.objects.create(
            workflow_run=self.wfr,
            text="to delete",
            created_by="tester",
            severity="ERROR",
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.delete(
            url,
            HTTP_AUTHORIZATION="Bearer fake.jwt.token",
        )
        self.assertEqual(response.status_code, 204)
        c.refresh_from_db()
        self.assertTrue(c.is_deleted)
        self.assertEqual(c.severity, "ERROR")

    @patch(
        "workflow_manager.viewsets.base.decode_rs256_jwt_payload_without_verification",
        return_value={"email": "other_user"},
    )
    def test_soft_delete_permission_denied(self, _mock_decode):
        c = Comment.objects.create(
            workflow_run=self.wfr, text="x", created_by="creator"
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.delete(
            url,
            HTTP_AUTHORIZATION="Bearer fake.jwt.token",
        )
        self.assertEqual(response.status_code, 403)

    def test_soft_delete_requires_bearer_token(self):
        c = Comment.objects.create(
            workflow_run=self.wfr, text="x", created_by="tester"
        )
        url = f"{self.endpoint}/{self.wfr.orcabus_id}/comment/{c.orcabus_id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 401)


class AnalysisRunCommentViewSetTestCase(TestCase):
    endpoint = f"/{api_base}analysisrun"

    def setUp(self):
        from workflow_manager.models import AnalysisRun
        from workflow_manager.tests.fixtures.sim_analysis import TestData

        TestData().assign_analysis()
        self.analysis_run = AnalysisRun.objects.first()

    def test_create_comment_parent_not_found(self):
        url = f"{self.endpoint}/anr.nonexistent123/comment/"
        response = self.client.post(
            url,
            data={"text": "x", "created_by": "u"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("AnalysisRun not found", response.json()["detail"])


class PayloadViewSetTestCase(TestCase):
    endpoint = f"/{api_base}payload"

    def test_payload_data_no_camel_case(self):
        """
        python manage.py test workflow_manager.tests.test_viewsets.PayloadViewSetTestCase.test_payload_data_no_camel_case
        """

        mock_payload = Payload.objects.create(
            payload_ref_id=str(uuid.uuid4()),
            version="1.0.0",
            data={
                "under_score": "foo",
                "key-with-dash": "bar",
                "PascalCase": "bash",
                "inputs": {
                    "forceGenome": True,
                    "genome_type": "alt",
                    "genome_version": "38",
                    "genomes": {
                        "GRCh38_umccr": {
                            "fai": "s3://reference-data/refdata/genomes/GRCh38_umccr/foo/bar/GRCh38.fa.fai"
                        }
                    }
                },
                "engineParameters": {
                    "logsUri": "s3://reference-data/refdata/logs/",
                    "logs_uri": "s3://underscore-data/refdata/logs/",
                }
            })

        response = self.client.get(f"{self.endpoint}/{mock_payload.orcabus_id}")

        logger.info(response.json())
        resp_data = response.json()['data']
        keys = resp_data.keys()

        self.assertEqual(response.status_code, 200, 'Expected a successful response')
        self.assertIn('under_score', keys)
        self.assertIn('key-with-dash', keys)
        self.assertIn('PascalCase', keys)
        self.assertIn('inputs', keys)
        self.assertIn('engineParameters', keys)

        inputs = resp_data['inputs']
        inputs_keys = inputs.keys()
        self.assertIn('forceGenome', inputs_keys)
        self.assertIn('genome_type', inputs_keys)
        self.assertIn('genome_version', inputs_keys)
        self.assertIn('genomes', inputs_keys)
        self.assertIn('GRCh38_umccr', inputs['genomes'].keys())

        engine_parameters = resp_data['engineParameters']
        engine_parameters_keys = engine_parameters.keys()
        self.assertIn('logsUri', engine_parameters_keys)
        self.assertIn('logs_uri', engine_parameters_keys)
