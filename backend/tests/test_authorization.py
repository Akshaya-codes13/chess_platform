import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.deps import (
    require_admin,
    require_roles,
    require_student,
    require_trainer,
)
from app.models import User
from tests.conftest import auth_headers

# No domain endpoints are role-restricted yet, so the dependencies are
# exercised through routes defined only for these tests.
rbac_app = FastAPI()


@rbac_app.get("/admin-only")
def admin_only(user: User = Depends(require_admin)):
    return {"role": user.role}


@rbac_app.get("/trainer-only")
def trainer_only(user: User = Depends(require_trainer)):
    return {"role": user.role}


@rbac_app.get("/student-only")
def student_only(user: User = Depends(require_student)):
    return {"role": user.role}


@rbac_app.get("/staff-only")
def staff_only(user: User = Depends(require_roles("admin", "trainer"))):
    return {"role": user.role}


ACCESS_MATRIX = {
    "/admin-only": {"admin"},
    "/trainer-only": {"trainer"},
    "/student-only": {"student"},
    "/staff-only": {"admin", "trainer"},
}


@pytest.fixture()
def rbac_client():
    return TestClient(rbac_app)


@pytest.fixture()
def users_by_role(create_user):
    return {
        role: create_user(role)[0]
        for role in ("admin", "trainer", "student")
    }


@pytest.mark.parametrize("path", ACCESS_MATRIX)
def test_role_access_matrix(rbac_client, users_by_role, path):
    for role, user in users_by_role.items():
        response = rbac_client.get(path, headers=auth_headers(user))

        if role in ACCESS_MATRIX[path]:
            assert response.status_code == 200, (path, role)
            assert response.json() == {"role": role}
        else:
            assert response.status_code == 403, (path, role)


@pytest.mark.parametrize("path", ACCESS_MATRIX)
def test_unauthenticated_requests_get_401(rbac_client, path):
    assert rbac_client.get(path).status_code == 401

    invalid = rbac_client.get(
        path, headers={"Authorization": "Bearer not-a-valid-token"}
    )
    assert invalid.status_code == 401


def test_all_roles_can_access_own_profile(client, users_by_role):
    for role, user in users_by_role.items():
        response = client.get("/auth/me", headers=auth_headers(user))

        assert response.status_code == 200
        assert response.json()["role"] == role


def test_require_roles_rejects_unknown_roles():
    with pytest.raises(ValueError):
        require_roles("superuser")

    with pytest.raises(ValueError):
        require_roles()
