# -*- coding: utf-8 -*-
"""api module for wsgi to AWS lambda

See README https://github.com/logandk/serverless-wsgi
"""
import logging

import serverless_wsgi

from workflow_manager.wsgi import application

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _get_request_details(event):
    """Return HTTP method and path from API Gateway v2 events, with v1 fallbacks."""
    if not isinstance(event, dict):
        return None, None

    request_context = event.get("requestContext")
    http_context = request_context.get("http") if isinstance(request_context, dict) else None

    http_method = None
    path = None
    if isinstance(http_context, dict):
        http_method = http_context.get("method")
        path = http_context.get("path")

    http_method = http_method or event.get("httpMethod")
    path = event.get("rawPath") or path or event.get("path")

    return http_method, path


def handler(event, context):
    """Lambda entrypoint for the API with exception logging for CloudWatch."""
    try:
        return serverless_wsgi.handle_request(application, event, context)
    except Exception as exc:
        remaining_ms = None
        if context is not None and hasattr(context, "get_remaining_time_in_millis"):
            remaining_ms = context.get_remaining_time_in_millis()

        request_id = getattr(context, "aws_request_id", None)
        http_method, path = _get_request_details(event)

        logger.exception(
            "API Lambda request failed: request_id=%s remaining_ms=%s method=%s path=%s error_type=%s",
            request_id,
            remaining_ms,
            http_method,
            path,
            type(exc).__name__,
        )
        raise
