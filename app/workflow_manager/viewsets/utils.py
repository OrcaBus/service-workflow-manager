from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

import jwt
from rest_framework.exceptions import AuthenticationFailed

from workflow_manager.models.workflow import Workflow
from workflow_manager.serializers.base import version_sort_key

logger = logging.getLogger(__name__)


def parse_bearer_raw_token_from_request(request, keyword: str = "Bearer") -> Optional[str]:
    """
    Extract the JWT string from ``Authorization: Bearer <token>``.

    Returns ``None`` if the header is missing or not a single Bearer token.
    """
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header:
        return None

    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != keyword.lower():
        return None

    raw_token = parts[1].strip()
    return raw_token or None


def decode_rs256_jwt_payload_without_verification(raw_token: str) -> dict[str, Any]:
    """
    Decode a JWT's payload with alg RS256. Signature is **not** verified.

    Use when an upstream layer (e.g. API Gateway) has already authenticated the caller;
    this only reads claims such as ``email``.
    """
    try:
        return jwt.decode(
            raw_token,
            options={"verify_signature": False},
            algorithms=["RS256"],
        )
    except jwt.PyJWTError as exc:
        logger.info("JWT decode failed: %s", exc)
        raise AuthenticationFailed("Invalid token.") from exc


def get_email_from_bearer_authorization(request, keyword: str = "Bearer") -> str:
    """
    Normalized ``email`` claim from ``Authorization: Bearer <jwt>``.

    Raises:
        AuthenticationFailed: Missing/malformed Bearer header, invalid token, or no email claim.
    """
    raw_token = parse_bearer_raw_token_from_request(request, keyword=keyword)
    if not raw_token:
        raise AuthenticationFailed("Authentication credentials were not provided.")
    payload = decode_rs256_jwt_payload_without_verification(raw_token)
    email = payload.get("email")
    if email and isinstance(email, str) and email.strip():
        return email.strip().lower()
    raise AuthenticationFailed("Token payload did not contain a valid email claim.")


def get_latest_workflows_by_name_group(
    workflows: Iterable[Workflow],
) -> Tuple[List[Workflow], Dict[str, List[Workflow]]]:
    """Group workflows by name (case-insensitive), pick highest version per group.

    Version ordering uses ``version_sort_key`` (semantic ``X.Y.Z``). Among equal versions,
    stable sort keeps the first occurrence as the "latest".

    Returns:
        ``latest_list``: one ``Workflow`` per group, ordered by sorted lowercase name key.
        ``history_map``: maps each chosen latest workflow's ``orcabus_id`` to the full
        list of workflows in that name group (all versions).
    """
    grouped: dict[str, list] = defaultdict(list)
    for w in workflows:
        grouped[w.name.lower()].append(w)

    latest_list: List[Workflow] = []
    history_map: Dict[str, List[Workflow]] = {}
    for name_key in sorted(grouped.keys()):
        group = grouped[name_key]
        group.sort(key=lambda w: version_sort_key(w.version), reverse=True)
        latest = group[0]
        latest_list.append(latest)
        history_map[latest.orcabus_id] = group

    return latest_list, history_map
