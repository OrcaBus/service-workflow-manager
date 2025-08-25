from workflow_manager_proc.domain.event import wru
from workflow_manager_proc.tests.case import WorkflowManagerProcUnitTestCase, logger


class WruSerdeUnitTests(WorkflowManagerProcUnitTestCase):

    def setUp(self) -> None:
        super(WruSerdeUnitTests, self).setUp()

    def test_model_serde(self):
        """
        python manage.py test workflow_manager_proc.tests.test_wru.WruSerdeUnitTests.test_model_serde
        """
        self.load_mock_wru_max()

        event: dict = self.event

        mock_obj_with_envelope: wru.AWSEvent = wru.AWSEvent.model_validate(event)

        # test model serialization
        logger.info(dict(mock_obj_with_envelope))
        logger.info("-" * 128)
        logger.info(mock_obj_with_envelope.model_dump(by_alias=False))
        logger.info("-" * 128)
        logger.info(mock_obj_with_envelope.model_dump(by_alias=True))  # by_alias=True make it to `detail-type`
        logger.info("-" * 128)
        logger.info(mock_obj_with_envelope.model_dump_json(by_alias=True))
        self.assertIsNotNone(mock_obj_with_envelope)

        mock_obj: wru.WorkflowRunUpdate = mock_obj_with_envelope.detail

        mock_event = mock_obj.model_dump(by_alias=True)
        logger.info(type(mock_event))
        self.assertIsInstance(mock_event, dict)  # assert that `mock_event` is some `dict` object

        # validate and deserialize from some dict object
        wrsc_envelope1 = wru.WorkflowRunUpdate.model_validate(mock_event)
        logger.info(wrsc_envelope1.model_dump(by_alias=True))

        # unpack and deserialize from some dict object
        wrsc_envelope2 = wru.WorkflowRunUpdate(**mock_event)
        logger.info(wrsc_envelope2.model_dump(by_alias=True))

        self.assertEqual(wrsc_envelope1, wrsc_envelope2)

    def test_wru_payload_without_ref_id(self):
        """
        python manage.py test workflow_manager_proc.tests.test_wru.WruSerdeUnitTests.test_wru_payload_without_ref_id
        """
        self.load_mock_wru_max()

        event: dict = self.event
        del event['detail']['payload']['refId']

        logger.info(event['detail']['payload'].keys())

        self.assertNotIn('refId', event['detail']['payload'].keys())

        mock_obj_with_envelope: wru.AWSEvent = wru.AWSEvent.model_validate(event)

        self.assertIsNotNone(mock_obj_with_envelope)
