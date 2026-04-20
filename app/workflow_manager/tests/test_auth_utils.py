import jwt
from django.test import TestCase, RequestFactory
from rest_framework.exceptions import AuthenticationFailed

from workflow_manager.viewsets.auth_utils import (
    parse_bearer_raw_token_from_request,
    decode_rs256_jwt_payload_without_verification,
    get_email_from_bearer_authorization,
)


class ParseBearerTokenTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _make_request(self, auth_header=None):
        request = self.factory.get("/")
        if auth_header is not None:
            request.META["HTTP_AUTHORIZATION"] = auth_header
        return request

    def test_missing_header_returns_none(self):
        request = self._make_request()
        self.assertIsNone(parse_bearer_raw_token_from_request(request))

    def test_empty_header_returns_none(self):
        request = self._make_request("")
        self.assertIsNone(parse_bearer_raw_token_from_request(request))

    def test_wrong_keyword_returns_none(self):
        request = self._make_request("Basic abc123")
        self.assertIsNone(parse_bearer_raw_token_from_request(request))

    def test_valid_bearer_token(self):
        request = self._make_request("Bearer mytoken123")
        self.assertEqual(parse_bearer_raw_token_from_request(request), "mytoken123")

    def test_custom_keyword(self):
        request = self._make_request("Token mytoken123")
        self.assertEqual(
            parse_bearer_raw_token_from_request(request, keyword="Token"),
            "mytoken123",
        )

    def test_too_many_parts_returns_none(self):
        request = self._make_request("Bearer token extra")
        self.assertIsNone(parse_bearer_raw_token_from_request(request))

    def test_whitespace_only_token_returns_none(self):
        request = self._make_request("Bearer  ")
        self.assertIsNone(parse_bearer_raw_token_from_request(request))


class DecodeJwtTests(TestCase):
    def test_valid_jwt(self):
        token = jwt.encode(
            {"email": "user@example.com", "sub": "123"},
            "secret",
            algorithm="HS256",
        )
        # decode without verification should still work for HS256 payload
        payload = decode_rs256_jwt_payload_without_verification(token)
        self.assertEqual(payload["email"], "user@example.com")

    def test_invalid_jwt_raises(self):
        with self.assertRaises(AuthenticationFailed):
            decode_rs256_jwt_payload_without_verification("not.a.valid.jwt")


class GetEmailFromBearerTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _make_request(self, auth_header=None):
        request = self.factory.get("/")
        if auth_header is not None:
            request.META["HTTP_AUTHORIZATION"] = auth_header
        return request

    def test_full_flow_returns_email(self):
        token = jwt.encode({"email": "Test@Example.COM"}, "secret", algorithm="HS256")
        request = self._make_request(f"Bearer {token}")
        email = get_email_from_bearer_authorization(request)
        self.assertEqual(email, "test@example.com")

    def test_missing_header_raises(self):
        request = self._make_request()
        with self.assertRaises(AuthenticationFailed):
            get_email_from_bearer_authorization(request)

    def test_no_email_claim_raises(self):
        token = jwt.encode({"sub": "123"}, "secret", algorithm="HS256")
        request = self._make_request(f"Bearer {token}")
        with self.assertRaises(AuthenticationFailed):
            get_email_from_bearer_authorization(request)

    def test_empty_email_claim_raises(self):
        token = jwt.encode({"email": "  "}, "secret", algorithm="HS256")
        request = self._make_request(f"Bearer {token}")
        with self.assertRaises(AuthenticationFailed):
            get_email_from_bearer_authorization(request)
