import logging
import uuid

from django.test import TestCase

from workflow_manager.models import Payload
from workflow_manager.urls.base import api_base

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PayloadViewSetTestCase(TestCase):
    endpoint = f"/{api_base}payload"

    def test_payload_data_no_camel_case(self):
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
                    },
                },
                "engineParameters": {
                    "logsUri": "s3://reference-data/refdata/logs/",
                    "logs_uri": "s3://underscore-data/refdata/logs/",
                },
            },
        )

        response = self.client.get(f"{self.endpoint}/{mock_payload.orcabus_id}")
        logger.info(response.json())
        resp_data = response.json()["data"]
        keys = resp_data.keys()

        self.assertEqual(response.status_code, 200, "Expected a successful response")
        self.assertIn("under_score", keys)
        self.assertIn("key-with-dash", keys)
        self.assertIn("PascalCase", keys)
        self.assertIn("inputs", keys)
        self.assertIn("engineParameters", keys)

        inputs = resp_data["inputs"]
        inputs_keys = inputs.keys()
        self.assertIn("forceGenome", inputs_keys)
        self.assertIn("genome_type", inputs_keys)
        self.assertIn("genome_version", inputs_keys)
        self.assertIn("genomes", inputs_keys)
        self.assertIn("GRCh38_umccr", inputs["genomes"].keys())

        engine_parameters = resp_data["engineParameters"]
        engine_parameters_keys = engine_parameters.keys()
        self.assertIn("logsUri", engine_parameters_keys)
        self.assertIn("logs_uri", engine_parameters_keys)
