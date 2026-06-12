from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

import api


class ApiHandlerTests(SimpleTestCase):
    def setUp(self):
        self.context = SimpleNamespace(
            aws_request_id="request-123",
            function_name="workflow-manager-api",
            log_stream_name="2026/04/24/[$LATEST]stream-123",
            get_remaining_time_in_millis=lambda: 1234,
        )
        self.event = {
            "httpMethod": "GET",
            "path": "/api/v1/workflows/",
        }

    def test_handler_passes_successful_response_through(self):
        expected_response = {"statusCode": 200, "body": "{}"}

        with patch(
            "api.serverless_wsgi.handle_request", return_value=expected_response
        ) as mock_handle_request:
            response = api.handler(self.event, self.context)

        self.assertEqual(response, expected_response)
        mock_handle_request.assert_called_once_with(
            api.application, self.event, self.context
        )

    def test_handler_logs_context_when_wsgi_handler_raises(self):
        error = RuntimeError("gateway timeout")

        with (
            patch("api.serverless_wsgi.handle_request", side_effect=error),
            patch("api.logger.exception") as mock_logger_exception,
        ):
            with self.assertRaises(RuntimeError):
                api.handler(self.event, self.context)

        mock_logger_exception.assert_called_once()
        message, *args = mock_logger_exception.call_args.args
        self.assertIn("API Lambda request failed", message)
        self.assertEqual(
            args,
            [
                "request-123",
                1234,
                "GET",
                "/api/v1/workflows/",
                "RuntimeError",
            ],
        )

    def test_handler_logs_http_api_v2_request_details_when_wsgi_handler_raises(self):
        error = RuntimeError("gateway timeout")
        event = {
            "rawPath": "/api/v1/workflows/",
            "requestContext": {
                "http": {
                    "method": "POST",
                    "path": "/stage/api/v1/workflows/",
                },
            },
        }

        with (
            patch("api.serverless_wsgi.handle_request", side_effect=error),
            patch("api.logger.exception") as mock_logger_exception,
        ):
            with self.assertRaises(RuntimeError):
                api.handler(event, self.context)

        mock_logger_exception.assert_called_once()
        message, *args = mock_logger_exception.call_args.args
        self.assertIn("API Lambda request failed", message)
        self.assertEqual(
            args,
            [
                "request-123",
                1234,
                "POST",
                "/api/v1/workflows/",
                "RuntimeError",
            ],
        )

    def test_handler_falls_back_to_http_api_context_path_when_raw_path_is_missing(self):
        error = RuntimeError("gateway timeout")
        event = {
            "requestContext": {
                "http": {
                    "method": "PATCH",
                    "path": "/api/v1/workflows/1/",
                },
            },
        }

        with (
            patch("api.serverless_wsgi.handle_request", side_effect=error),
            patch("api.logger.exception") as mock_logger_exception,
        ):
            with self.assertRaises(RuntimeError):
                api.handler(event, self.context)

        mock_logger_exception.assert_called_once()
        _message, *args = mock_logger_exception.call_args.args
        self.assertEqual(
            args,
            [
                "request-123",
                1234,
                "PATCH",
                "/api/v1/workflows/1/",
                "RuntimeError",
            ],
        )
