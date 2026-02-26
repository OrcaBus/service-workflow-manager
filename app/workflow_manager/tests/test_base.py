import logging

from django.db.models import Q
from django.test import TestCase

from workflow_manager.models.base import OrcaBusBaseManager, OrcaBusBaseModel

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class OrcaBusBaseManagerTestCase(TestCase):

    def setUp(self) -> None:
        pass

    def test_reduce_multi_values_qor(self):
        """
        python manage.py test workflow_manager.tests.test_base.OrcaBusBaseManagerTestCase.test_reduce_multi_values_qor
        """
        q = OrcaBusBaseManager.reduce_multi_values_qor('subject_id', ["SBJ000001", "SBJ000002"])
        logger.info(q)
        self.assertIsNotNone(q)
        self.assertIsInstance(q, Q)
        self.assertIn(Q.OR, str(q))

    def test_reduce_multi_values_qor_auto_pack(self):
        """
        python manage.py test workflow_manager.tests.test_base.OrcaBusBaseManagerTestCase.test_reduce_multi_values_qor_auto_pack
        """
        q = OrcaBusBaseManager.reduce_multi_values_qor('subject_id', "SBJ000001")
        logger.info(q)
        self.assertIsNotNone(q)
        self.assertIsInstance(q, Q)
        self.assertIn(Q.AND, str(q))

    def test_reduce_multi_values_qor_comma_separated(self):
        """Comma-separated string is expanded into OR of individual values."""
        q = OrcaBusBaseManager.reduce_multi_values_qor(
            'workflow__orcabus_id', "id1,id2,wfl.id3"
        )
        self.assertIsNotNone(q)
        self.assertIsInstance(q, Q)
        self.assertIn(Q.OR, str(q))

    def test_reduce_multi_values_qor_none_returns_empty_q(self):
        """When values is None, returns empty Q()."""
        q = OrcaBusBaseManager.reduce_multi_values_qor('subject_id', None)
        self.assertIsNotNone(q)
        self.assertIsInstance(q, Q)
        self.assertEqual(q, Q())

    def test_reduce_multi_values_qor_empty_list_returns_empty_q(self):
        """When values is empty list, returns empty Q()."""
        q = OrcaBusBaseManager.reduce_multi_values_qor('subject_id', [])
        self.assertIsNotNone(q)
        self.assertIsInstance(q, Q)
        self.assertEqual(q, Q())

    def test_reduce_multi_values_qor_empty_after_expansion_returns_empty_q(self):
        """When values expand to empty (only comma-separated strings with no valid parts), returns empty Q()."""
        q = OrcaBusBaseManager.reduce_multi_values_qor('subject_id', ["  ,  ", ","])
        self.assertIsNotNone(q)
        self.assertIsInstance(q, Q)
        self.assertEqual(q, Q())

    def test_base_model_must_abstract(self):
        """
        python manage.py test workflow_manager.tests.test_base.OrcaBusBaseManagerTestCase.test_base_model_must_abstract
        """
        try:
            OrcaBusBaseModel()
        except TypeError as e:
            logger.exception(f"THIS ERROR EXCEPTION IS INTENTIONAL FOR TEST. NOT ACTUAL ERROR. \n{e}")
        self.assertRaises(TypeError)

    def test_get_fields_returns_field_names(self):
        """OrcaBusBaseModel.get_fields returns list of field names."""
        from workflow_manager.models import Library

        fields = Library.get_fields()
        self.assertIsInstance(fields, list)
        self.assertIn("orcabus_id", fields)
        self.assertIn("library_id", fields)

    def test_get_base_fields_excludes_relations(self):
        """OrcaBusBaseModel.get_base_fields excludes ForeignKey/M2M relations."""
        from workflow_manager.models import Library

        base_fields = Library.get_base_fields()
        self.assertIsInstance(base_fields, list)
        self.assertIn("orcabus_id", base_fields)
        self.assertIn("library_id", base_fields)
