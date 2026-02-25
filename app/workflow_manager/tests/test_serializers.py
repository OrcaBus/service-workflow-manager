"""
Tests for serializers in workflow_manager.serializers
"""

from django.test import TestCase

from workflow_manager.models import Library
from rest_framework import serializers

from workflow_manager.serializers.base import (
    OrcabusIdListField,
    OrcabusIdListUtils,
    SerializersBase,
    to_camel_case,
)
from workflow_manager.tests.factories import LibraryFactory


class ToCamelCaseTests(TestCase):
    def test_snake_to_camel(self):
        self.assertEqual(to_camel_case("snake_case"), "snakeCase")
        self.assertEqual(to_camel_case("my_field_name"), "myFieldName")

    def test_dash_to_camel(self):
        self.assertEqual(to_camel_case("some-dash"), "someDash")

    def test_first_component_lowercase(self):
        self.assertEqual(to_camel_case("First_upper"), "firstUpper")


class SerializersBaseTests(TestCase):
    def test_to_representation_default_no_camel_case(self):
        lib = LibraryFactory()
        from workflow_manager.serializers.library import LibrarySerializer

        serializer = LibrarySerializer(lib)
        data = serializer.data
        self.assertIn("orcabus_id", data)
        self.assertIn("library_id", data)
        self.assertNotIn("orcabusId", data)

    def test_to_representation_with_camel_case(self):
        lib = LibraryFactory()
        from workflow_manager.serializers.library import LibrarySerializer

        serializer = LibrarySerializer(lib, camel_case_data=True)
        data = serializer.data
        self.assertIn("orcabusId", data)
        self.assertIn("libraryId", data)


class OrcabusIdListUtilsTests(TestCase):
    def test_normalize_none(self):
        self.assertEqual(OrcabusIdListUtils.normalize(None), [])

    def test_normalize_string_comma_separated(self):
        self.assertEqual(
            OrcabusIdListUtils.normalize("id1, id2, id3"),
            ["id1", "id2", "id3"],
        )

    def test_normalize_list_of_values(self):
        self.assertEqual(
            OrcabusIdListUtils.normalize(["id1", "id2"]),
            ["id1", "id2"],
        )

    def test_normalize_list_with_comma_in_single_element(self):
        self.assertEqual(
            OrcabusIdListUtils.normalize(["id1,id2,id3"]),
            ["id1", "id2", "id3"],
        )

    def test_normalize_single_non_list_value(self):
        self.assertEqual(OrcabusIdListUtils.normalize("single_id"), ["single_id"])

    def test_normalize_filters_empty_strings(self):
        self.assertEqual(
            OrcabusIdListUtils.normalize(["id1", "", "  ", "id2"]),
            ["id1", "id2"],
        )


class OrcabusIdListFieldTests(TestCase):
    def test_to_internal_value_normalizes_string(self):
        field = OrcabusIdListField(child=serializers.CharField())
        result = field.to_internal_value("id1,id2,id3")
        self.assertEqual(result, ["id1", "id2", "id3"])

    def test_to_internal_value_normalizes_list_with_comma_in_element(self):
        field = OrcabusIdListField(child=serializers.CharField())
        result = field.to_internal_value(["id1,id2,id3"])
        self.assertEqual(result, ["id1", "id2", "id3"])


class UpdatableAnalysisSerializerTests(TestCase):
    def setUp(self):
        from workflow_manager.models import Analysis, AnalysisContext, Workflow
        from workflow_manager.models.analysis_context import AnalysisContextUseCase

        self.ctx = AnalysisContext.objects.create(
            name="ctx1", usecase=AnalysisContextUseCase.COMPUTE.value
        )
        self.wfl = Workflow.objects.create(
            name="wfl", version="1.0", execution_engine="ICA",
            execution_engine_pipeline_id="pipe1"
        )
        self.analysis = Analysis.objects.create(
            analysis_name="TestAnalysis",
            analysis_version="1.0",
            description="Original desc",
        )
        self.analysis.contexts.add(self.ctx)
        self.analysis.workflows.add(self.wfl)

    def test_update_empty_description_removed(self):
        from workflow_manager.serializers.analysis import UpdatableAnalysisSerializer

        serializer = UpdatableAnalysisSerializer(
            self.analysis,
            data={"description": "", "status": "ACTIVE"},
            partial=True,
        )
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.description, "Original desc")

    def test_update_contexts(self):
        from workflow_manager.models import AnalysisContext
        from workflow_manager.models.analysis_context import AnalysisContextUseCase
        from workflow_manager.serializers.analysis import UpdatableAnalysisSerializer

        ctx2 = AnalysisContext.objects.create(
            name="ctx2", usecase=AnalysisContextUseCase.COMPUTE.value
        )
        serializer = UpdatableAnalysisSerializer(
            self.analysis,
            data={"contexts": [self.ctx.orcabus_id, ctx2.orcabus_id]},
            partial=True,
        )
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.contexts.count(), 2)

    def test_update_workflows(self):
        from workflow_manager.models import Workflow
        from workflow_manager.serializers.analysis import UpdatableAnalysisSerializer

        wfl2 = Workflow.objects.create(
            name="wfl2", version="1.0", execution_engine="ICA",
            execution_engine_pipeline_id="pipe2"
        )
        serializer = UpdatableAnalysisSerializer(
            self.analysis,
            data={"workflows": [self.wfl.orcabus_id, wfl2.orcabus_id]},
            partial=True,
        )
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.workflows.count(), 2)


class AnalysisRunSerializerTests(TestCase):
    def test_get_current_state_none_when_no_states(self):
        from workflow_manager.models import AnalysisRun
        from workflow_manager.serializers.analysis_run import AnalysisRunSerializer

        ar = AnalysisRun.objects.create(analysis_run_name="TestRun")
        serializer = AnalysisRunSerializer(ar)
        data = serializer.data
        self.assertIsNone(data["current_state"])

    def test_get_states_empty_list_when_no_states(self):
        from workflow_manager.models import AnalysisRun
        from workflow_manager.serializers.analysis_run import AnalysisRunDetailSerializer

        ar = AnalysisRun.objects.create(analysis_run_name="TestRun")
        serializer = AnalysisRunDetailSerializer(ar)
        data = serializer.data
        self.assertEqual(data["states"], [])
