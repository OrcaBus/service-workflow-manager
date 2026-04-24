# -*- coding: utf-8 -*-
"""api module for wsgi to AWS lambda

See README https://github.com/logandk/serverless-wsgi
"""
import logging

import serverless_wsgi

from workflow_manager.wsgi import application

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Lambda entrypoint for the API with exception logging for CloudWatch."""
    try:
        return serverless_wsgi.handle_request(application, event, context)
    except Exception as exc:
        remaining_ms = None
        if context is not None and hasattr(context, "get_remaining_time_in_millis"):
            remaining_ms = context.get_remaining_time_in_millis()

        request_id = getattr(context, "aws_request_id", None)
        http_method = event.get("httpMethod") if isinstance(event, dict) else None
        path = event.get("path") if isinstance(event, dict) else None

        logger.exception(
            "API Lambda request failed: request_id=%s remaining_ms=%s method=%s path=%s error_type=%s",
            request_id,
            remaining_ms,
            http_method,
            path,
            type(exc).__name__,
        )
        raise
