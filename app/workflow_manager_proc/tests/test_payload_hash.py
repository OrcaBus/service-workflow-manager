import json
import logging

from django.test import TestCase
from workflow_manager_proc.services.event_utils import hash_payload_data

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PayloadHashUnitTestCase(TestCase):

    def test_order(self) -> None:
        """
        python manage.py test workflow_manager_proc.tests.test_payload_hash.PayloadHashUnitTestCase.test_order
        """
        logger.info("Testing JSON element order...")
        json_1 = """
        {
            "key1": "one",
            "key2": "two",
            "key3": "three"
        }
        """
        json_2 = """
        {
            "key2": "two",
            "key1": "one",
            "key3": "three"
        }
        """
        json_1_hash = hash_payload_data(json.loads(json_1))
        json_2_hash = hash_payload_data(json.loads(json_2))

        self.assertEqual(json_1_hash, json_2_hash, "Hashes to not match!")

        json_1 = """
        {
            "key1": "one",
            "key2": 2,
            "key3": false
        }
        """
        json_2 = """
        {
            "key2": 2,
            "key1": "one",
            "key3": false
        }
        """
        json_1_hash = hash_payload_data(json.loads(json_1))
        json_2_hash = hash_payload_data(json.loads(json_2))

        self.assertEqual(json_1_hash, json_2_hash, "Hashes to not match!")

        json_1 = """
        {
            "key1": true,
            "key2": true,
            "key3": false
        }
        """
        json_2 = """
        {
            "key2": true,
            "key1": true,
            "key3": false
        }
        """
        json_1_hash = hash_payload_data(json.loads(json_1))
        json_2_hash = hash_payload_data(json.loads(json_2))

        self.assertEqual(json_1_hash, json_2_hash, "Hashes to not match!")

    def test_formatting(self) -> None:
        """
        python manage.py test workflow_manager_proc.tests.test_payload_hash.PayloadHashUnitTestCase.test_formatting
        """
        logger.info("Testing JSON formatting...")
        json_1 = """
        {"key1":"one","key2":"two","key3":"three"}
        """
        json_2 = """
        {
            "key2": "two",
            "key1": "one",
            "key3": "three"
        }
        """
        json_1_hash = hash_payload_data(json.loads(json_1))
        json_2_hash = hash_payload_data(json.loads(json_2))

        self.assertEqual(json_1_hash, json_2_hash, "Hashes to not match!")

        json_1 = """
        {"key": ["one","two","three"]}
        """
        json_2 = """
        {
            "key":     ["one",  "two",      "three"]
        }
        """
        json_3 = """
        {
            "key": [
                "one",
                "two",
                "three"
            ]
        }
        """
        json_1_hash = hash_payload_data(json.loads(json_1))
        json_2_hash = hash_payload_data(json.loads(json_2))
        json_3_hash = hash_payload_data(json.loads(json_3))

        self.assertTrue(json_1_hash == json_2_hash == json_3_hash, "Hashes to not match!")

    def test_arrays(self) -> None:
        """
        python manage.py test workflow_manager_proc.tests.test_payload_hash.PayloadHashUnitTestCase.test_arrays
        """
        logger.info("Testing JSON arrays (order matters!)...")
        json_1 = """
        {"key": ["one","two","three"]}
        """
        json_2 = """
        {"key": ["two", "one", "three"]}
        """
        json_1_hash = hash_payload_data(json.loads(json_1))
        json_2_hash = hash_payload_data(json.loads(json_2))

        self.assertNotEqual(json_1_hash, json_2_hash, "Hashes match!")

        json_1 = """
        {"key": ["one",2,false]}
        """
        json_2 = """
        {"key": ["one", 2, true]}
        """
        json_1_hash = hash_payload_data(json.loads(json_1))
        json_2_hash = hash_payload_data(json.loads(json_2))

        self.assertNotEqual(json_1_hash, json_2_hash, "Hashes match!")

    def test_null(self) -> None:
        """
        python manage.py test workflow_manager_proc.tests.test_payload_hash.PayloadHashUnitTestCase.test_null
        """
        logger.info("Testing JSON null element...")
        json_1 = """
        {
            "key1": "one",
            "key2": null,
            "key3": "three"
        }
        """
        json_2 = """
        {
            "key1": "one",
            "key3": "three"
        }
        """
        json_1_hash = hash_payload_data(json.loads(json_1))
        json_2_hash = hash_payload_data(json.loads(json_2))

        self.assertNotEqual(json_1_hash, json_2_hash, "Hashes do not match!")
        json_1 = """
        {"key": ["one", null, 3]}
        """
        json_2 = """
        {"key": ["one", 3]}
        """
        json_1_hash = hash_payload_data(json.loads(json_1))
        json_2_hash = hash_payload_data(json.loads(json_2))

        self.assertNotEqual(json_1_hash, json_2_hash, "Hashes do not match!")

    def test_complex_json(self) -> None:
        """
        python manage.py test workflow_manager_proc.tests.test_payload_hash.PayloadHashUnitTestCase.test_complex_json
        """
        logger.info("Testing complex JSON...")
        json_1 = """
        {
            "key": "value",
            "another-key": 2,
            "some-array": [1, {"foo":"bar", "bar":"foo"}, 3, [4], "this works too"],
            "another-array": [
                {
                    "key": ["one","two","three"],
                    "key2": "bar"
                },
                {
                    "key": ["two","one","three"],
                    "key2": "bar"
                },
                {
                    "key": [1,2,3]
                }
            ],
            "more": [null, true, false]
        }
        """
        json_2 = """
        {
            "another-key": 2,
            "key": "value",
            "another-array": [
                {
                    "key": ["one","two","three"],
                    "key2": "bar"
                },
                {
                    "key2": "bar",
                    "key": ["two","one","three"]
                },
                {
                    "key":      [1,  2,  3],
                    "key2": null
                }
            ],
            "some-array": [1, {"bar":"foo", "foo":"bar"}, 3, [4], "this works too"],
            "more": [null, true, false]
        }
        """
        json_1_hash = hash_payload_data(json.loads(json_1))
        json_2_hash = hash_payload_data(json.loads(json_2))

        self.assertNotEqual(json_1_hash, json_2_hash, "Hashes do not match!")
