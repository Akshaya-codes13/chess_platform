"""JWT handling after the python-jose -> PyJWT switch.

Tokens already issued (by python-jose) must keep working, and the decoder
must still reject forged, unsigned, expired and wrong-purpose tokens.
"""

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_purpose_token,
    decode_access_token,
    decode_purpose_token,
)


def _b64(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_access_token_round_trip():
    subject = str(uuid.uuid4())
    payload = decode_access_token(create_access_token(subject))

    assert payload["sub"] == subject
    assert payload["type"] == "access"
    assert isinstance(payload["exp"], int) and isinstance(payload["iat"], int)


def test_purpose_token_keeps_extra_claims_and_type():
    token = create_purpose_token("user-1", "password_reset", timedelta(minutes=5), {"pwd": "abc"})

    payload = decode_purpose_token(token, "password_reset")
    assert payload["pwd"] == "abc"
    assert decode_purpose_token(token, "email_verification") is None
    # Purpose tokens are never accepted as access tokens, and vice versa.
    assert decode_access_token(token) is None
    assert decode_purpose_token(create_access_token("user-1"), "password_reset") is None


def test_tokens_issued_by_python_jose_still_validate():
    jose_jwt = pytest.importorskip("jose.jwt", reason="python-jose is not installed")
    now = datetime.now(timezone.utc)
    legacy = jose_jwt.encode(
        {"sub": "legacy-user", "iat": now, "exp": now + timedelta(minutes=5), "type": "access"},
        settings.secret_key,
        algorithm=ALGORITHM,
    )

    assert decode_access_token(legacy)["sub"] == "legacy-user"


def test_rejects_wrong_key_unsigned_and_expired_tokens():
    now = datetime.now(timezone.utc)
    claims = {"sub": "user-1", "iat": now, "exp": now + timedelta(minutes=5), "type": "access"}

    wrong_key = jwt.encode(claims, "another-secret-key-" + "x" * 32, algorithm=ALGORITHM)
    unsigned = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64({**claims, 'iat': 0, 'exp': 2**31})}."
    expired = create_access_token("user-1", timedelta(seconds=-1))

    for token in (wrong_key, unsigned, expired, "", "a.b.c"):
        assert decode_access_token(token) is None
