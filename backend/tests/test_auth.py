from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models import RefreshToken, User
from app.services import auth_service, email_service
from tests.conftest import auth_headers, make_password


@pytest.fixture()
def sent_emails(monkeypatch):
    """Capture tokens passed to the email service instead of sending them."""
    sent = {"verification": [], "password_reset": []}

    monkeypatch.setattr(
        email_service,
        "send_verification_email",
        lambda email, token: sent["verification"].append((email, token)),
    )
    monkeypatch.setattr(
        email_service,
        "send_password_reset_email",
        lambda email, token: sent["password_reset"].append((email, token)),
    )
    return sent


def login(client, email, password):
    return client.post(
        "/auth/login", json={"email": email, "password": password}
    )


def get_user(email):
    session = SessionLocal()
    try:
        return session.scalar(select(User).where(User.email == email))
    finally:
        session.close()


# Registration and login

def test_register_creates_unverified_student(client, unique_email, sent_emails):
    response = client.post(
        "/auth/register",
        json={
            "email": unique_email,
            "password": make_password(),
            "full_name": "New Student",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == unique_email
    assert body["role"] == "student"
    assert body["is_verified"] is False
    assert "password" not in body and "password_hash" not in body
    assert [email for email, _ in sent_emails["verification"]] == [unique_email]


def test_register_duplicate_email_conflicts(client, create_user):
    user, _ = create_user()

    response = client.post(
        "/auth/register",
        json={
            "email": user.email.upper(),
            "password": make_password(),
            "full_name": "Duplicate",
        },
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "password", ["short1", "lettersonly", "1234567890"]
)
def test_register_rejects_weak_password(client, unique_email, password):
    response = client.post(
        "/auth/register",
        json={
            "email": unique_email,
            "password": password,
            "full_name": "Weak Password",
        },
    )

    assert response.status_code == 422


def test_login_success_and_failures(client, create_user):
    user, password = create_user()

    response = login(client, user.email, password)
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"

    wrong_password = login(client, user.email, "Wrong-password-1")
    unknown_email = login(client, "nobody-here@example.com", password)

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


# Access tokens

def test_me_returns_current_user(client, create_user):
    user, password = create_user()
    tokens = login(client, user.email, password).json()

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == user.email
    assert "password_hash" not in response.json()


def test_me_requires_authentication(client):
    assert client.get("/auth/me").status_code == 401


def test_me_rejects_invalid_tokens(client, create_user):
    user, _ = create_user()
    valid = create_access_token(str(user.id))
    expired = create_access_token(str(user.id), timedelta(seconds=-1))
    tampered = valid[:-2] + ("AA" if valid[-2:] != "AA" else "BB")
    wrong_type = auth_service.create_password_reset_token(user)

    for token in ["not-a-jwt", expired, tampered, wrong_type]:
        response = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401


# Refresh tokens

def test_refresh_rotation_and_reuse_detection(client, create_user):
    user, password = create_user()
    original = login(client, user.email, password).json()

    rotated = client.post(
        "/auth/refresh", json={"refresh_token": original["refresh_token"]}
    )
    assert rotated.status_code == 200
    rotated = rotated.json()
    assert rotated["refresh_token"] != original["refresh_token"]

    reused = client.post(
        "/auth/refresh", json={"refresh_token": original["refresh_token"]}
    )
    assert reused.status_code == 401

    # Replaying a revoked token revokes the whole session family.
    after_reuse = client.post(
        "/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
    )
    assert after_reuse.status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        "garbage",
        "00000000-0000-0000-0000-000000000000.unknown",
        "x" * 300,
    ],
)
def test_refresh_rejects_invalid_tokens(client, token):
    response = client.post("/auth/refresh", json={"refresh_token": token})

    assert response.status_code in {401, 422}


def test_logout_revokes_refresh_token(client, create_user):
    user, password = create_user()
    tokens = login(client, user.email, password).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    unauthenticated = client.post(
        "/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert unauthenticated.status_code == 401

    response = client.post(
        "/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )
    assert response.status_code == 200

    refreshed = client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 401


# Email verification

def test_email_verification_flow(client, unique_email, sent_emails):
    client.post(
        "/auth/register",
        json={
            "email": unique_email,
            "password": make_password(),
            "full_name": "Verify Me",
        },
    )
    [(_, token)] = sent_emails["verification"]

    response = client.post("/auth/verify-email", json={"token": token})
    assert response.status_code == 200
    assert get_user(unique_email).is_verified is True

    reused = client.post("/auth/verify-email", json={"token": token})
    assert reused.status_code == 400


def test_email_verification_rejects_bad_tokens(client, create_user):
    user, _ = create_user()
    expired = auth_service.create_email_verification_token(
        user, timedelta(seconds=-1)
    )
    access_token = create_access_token(str(user.id))

    for token in [expired, access_token, "not-a-token"]:
        response = client.post("/auth/verify-email", json={"token": token})
        assert response.status_code == 400

    assert get_user(user.email).is_verified is False


def test_request_email_verification(client, create_user, sent_emails):
    user, _ = create_user()

    response = client.post(
        "/auth/verify-email/request", headers=auth_headers(user)
    )
    assert response.status_code == 202
    [(email, token)] = sent_emails["verification"]
    assert email == user.email

    client.post("/auth/verify-email", json={"token": token})

    again = client.post(
        "/auth/verify-email/request", headers=auth_headers(user)
    )
    assert again.status_code == 400

    assert client.post("/auth/verify-email/request").status_code == 401


# Password reset

def test_password_reset_flow(client, create_user, sent_emails):
    user, old_password = create_user()
    old_tokens = login(client, user.email, old_password).json()

    response = client.post(
        "/auth/password-reset/request", json={"email": user.email}
    )
    assert response.status_code == 202
    [(email, token)] = sent_emails["password_reset"]
    assert email == user.email

    new_password = make_password()
    confirmed = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": new_password},
    )
    assert confirmed.status_code == 200

    assert login(client, user.email, old_password).status_code == 401
    assert login(client, user.email, new_password).status_code == 200

    # Existing refresh tokens are revoked by the reset.
    refreshed = client.post(
        "/auth/refresh", json={"refresh_token": old_tokens["refresh_token"]}
    )
    assert refreshed.status_code == 401

    # The token is single-use.
    reused = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": make_password()},
    )
    assert reused.status_code == 400


def test_password_reset_request_does_not_reveal_accounts(
    client, create_user, sent_emails
):
    user, _ = create_user()

    known = client.post(
        "/auth/password-reset/request", json={"email": user.email}
    )
    unknown = client.post(
        "/auth/password-reset/request",
        json={"email": "nobody-here@example.com"},
    )

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [email for email, _ in sent_emails["password_reset"]] == [user.email]


def test_password_reset_rejects_bad_tokens(client, create_user):
    user, password = create_user()
    expired = auth_service.create_password_reset_token(
        user, timedelta(seconds=-1)
    )
    verification = auth_service.create_email_verification_token(user)

    for token in [expired, verification, "not-a-token"]:
        response = client.post(
            "/auth/password-reset/confirm",
            json={"token": token, "new_password": make_password()},
        )
        assert response.status_code == 400

    weak = client.post(
        "/auth/password-reset/confirm",
        json={
            "token": auth_service.create_password_reset_token(user),
            "new_password": "lettersonly",
        },
    )
    assert weak.status_code == 422

    assert login(client, user.email, password).status_code == 200


def test_password_reset_revokes_all_refresh_tokens(create_user):
    user, password = create_user()
    session = SessionLocal()

    try:
        db_user = session.get(User, user.id)
        auth_service.issue_tokens(session, db_user)
        auth_service.issue_tokens(session, db_user)
        token = auth_service.create_password_reset_token(db_user)

        assert auth_service.reset_password(session, token, make_password())

        active = session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.is_revoked.is_(False),
            )
        ).all()
        assert active == []
    finally:
        session.close()


# Rate limiting

@pytest.fixture()
def low_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", True)
    monkeypatch.setattr(settings, "auth_rate_limit_requests", 2)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)


@pytest.mark.parametrize(
    "path, payload",
    [
        ("/auth/login", {"email": "nobody-here@example.com", "password": "x"}),
        ("/auth/refresh", {"refresh_token": "garbage"}),
        ("/auth/register", {"email": "bad", "password": "x", "full_name": "x"}),
        ("/auth/password-reset/request", {"email": "nobody-here@example.com"}),
    ],
)
def test_sensitive_endpoints_are_rate_limited(
    client, low_rate_limit, path, payload
):
    statuses = [client.post(path, json=payload).status_code for _ in range(3)]

    assert 429 not in statuses[:2]
    assert statuses[2] == 429

    limited = client.post(path, json=payload)
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 1


def test_rate_limits_are_tracked_per_endpoint(client, low_rate_limit):
    for _ in range(3):
        client.post("/auth/refresh", json={"refresh_token": "garbage"})

    response = login(client, "nobody-here@example.com", "x")
    assert response.status_code == 401


def test_authenticated_requests_are_not_rate_limited(
    client, create_user, low_rate_limit
):
    user, _ = create_user()

    for _ in range(5):
        response = client.get("/auth/me", headers=auth_headers(user))
        assert response.status_code == 200


def test_rate_limit_can_be_disabled(client, low_rate_limit, monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", False)

    for _ in range(5):
        response = login(client, "nobody-here@example.com", "x")
        assert response.status_code == 401


# Demo login

@pytest.fixture()
def demo_accounts(create_user, monkeypatch):
    """Point the demo account emails at throwaway users and enable demo login."""
    users = {role: create_user(role)[0] for role in ("admin", "trainer", "student")}
    for role, user in users.items():
        monkeypatch.setitem(auth_service.DEMO_ACCOUNT_EMAILS, role, user.email)
    monkeypatch.setattr(settings, "demo_login_enabled", True)
    return users


def test_demo_login_is_disabled_by_default(client, monkeypatch):
    monkeypatch.setattr(settings, "demo_login_enabled", False)

    assert client.get("/auth/demo").json() == {"enabled": False, "accounts": []}
    assert client.post("/auth/demo-login", json={"role": "student"}).status_code == 404


def test_demo_accounts_are_listed_when_enabled(client, demo_accounts):
    body = client.get("/auth/demo").json()

    assert body["enabled"] is True
    assert [account["role"] for account in body["accounts"]] == [
        "admin",
        "trainer",
        "student",
    ]
    assert body["accounts"][0]["email"] == demo_accounts["admin"].email
    assert all("password" not in str(account) for account in body["accounts"])


@pytest.mark.parametrize("role", ["admin", "trainer", "student"])
def test_demo_login_signs_in_as_the_role(client, demo_accounts, role):
    response = client.post("/auth/demo-login", json={"role": role})

    assert response.status_code == 200
    tokens = response.json()
    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.json()["email"] == demo_accounts[role].email
    assert client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).status_code == 200


def test_demo_login_rejects_unknown_role(client, demo_accounts):
    response = client.post("/auth/demo-login", json={"role": "superuser"})

    assert response.status_code == 422


def test_demo_login_ignores_account_with_wrong_role(
    client, demo_accounts, monkeypatch
):
    # A student account must never be handed out as the admin demo.
    monkeypatch.setitem(
        auth_service.DEMO_ACCOUNT_EMAILS, "admin", demo_accounts["student"].email
    )

    assert client.post("/auth/demo-login", json={"role": "admin"}).status_code == 404
    roles = [account["role"] for account in client.get("/auth/demo").json()["accounts"]]
    assert roles == ["trainer", "student"]


def test_demo_login_skips_inactive_accounts(client, demo_accounts):
    session = SessionLocal()
    try:
        session.get(User, demo_accounts["trainer"].id).is_active = False
        session.commit()
    finally:
        session.close()

    assert client.post("/auth/demo-login", json={"role": "trainer"}).status_code == 404


def test_demo_login_is_never_served_in_production(client, demo_accounts, monkeypatch):
    # Startup validation rejects this combination; the endpoints refuse it
    # too, in case the flag is changed on a running production process.
    monkeypatch.setattr(settings, "app_env", "production")

    assert client.get("/auth/demo").json() == {"enabled": False, "accounts": []}
    for role in ("admin", "trainer", "student"):
        response = client.post("/auth/demo-login", json={"role": role})
        assert response.status_code == 404
        assert "access_token" not in response.json()
