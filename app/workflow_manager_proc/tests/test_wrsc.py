import json
import os

from workflow_manager_proc.domain.event.wrsc import AWSEvent, WorkflowRunStateChange
from workflow_manager_proc.tests.case import WorkflowManagerProcUnitTestCase, logger


class WRSCUnitTests(WorkflowManagerProcUnitTestCase):

    def setUp(self) -> None:
        super(WRSCUnitTests, self).setUp()

    def test_model_serde(self):
        """
        python manage.py test workflow_manager_proc.tests.test_wrsc.WRSCUnitTests.test_model_serde
        """

        script_dir = os.path.dirname(__file__)
        rel_path = "fixtures/WRSC_max.json"
        logger.info(f"Loading test event data from {rel_path}")
        abs_file_path = os.path.join(script_dir, rel_path)
        with open(abs_file_path) as f:
            file_content = f.read()

        event: dict = json.loads(file_content)

        mock_obj_with_envelope: AWSEvent = AWSEvent.model_validate(event)

        # test model serialization
        logger.info(dict(mock_obj_with_envelope))
        logger.info("-" * 128)
        logger.info(mock_obj_with_envelope.model_dump(by_alias=False))
        logger.info("-" * 128)
        logger.info(mock_obj_with_envelope.model_dump(by_alias=True))  # by_alias=True make it to `detail-type`
        logger.info("-" * 128)
        logger.info(mock_obj_with_envelope.model_dump_json(by_alias=True))
        self.assertIsNotNone(mock_obj_with_envelope)

        mock_obj: WorkflowRunStateChange = mock_obj_with_envelope.detail

        mock_event = mock_obj.model_dump(by_alias=True)
        logger.info(type(mock_event))
        self.assertIsInstance(mock_event, dict)  # assert that `mock_event` is some `dict` object

        # validate and deserialize from some dict object
        wrsc_envelope1 = WorkflowRunStateChange.model_validate(mock_event)
        logger.info(wrsc_envelope1.model_dump(by_alias=True))

        # unpack and deserialize from some dict object
        wrsc_envelope2 = WorkflowRunStateChange(**mock_event)
        logger.info(wrsc_envelope2.model_dump(by_alias=True))

        self.assertEqual(wrsc_envelope1, wrsc_envelope2)
