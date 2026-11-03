"""M12: posts (articles, blogs, photos), image uploads and feedback."""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import Notification, StudentProfile, TrainerProfile
from tests.student_world import *  # noqa: F401,F403
from tests.student_world import _user, auth_headers

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


@pytest.fixture(autouse=True)
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    return tmp_path


def upload(api, headers, data=PNG, name="board.png"):
    return api.post("/content/media", files={"file": (name, data, "image/png")}, headers=headers)


def create_post(api, headers, **body):
    payload = {"title": "Opening principles", "type": "article", "content": "Control the centre.", **body}
    return api.post("/content/posts", json=payload, headers=headers)


# --- Posts ---------------------------------------------------------------------


def test_publish_and_view_workflow(api, world):
    trainer, student = world.trainer_headers, world.headers["a"]

    draft = create_post(api, trainer)
    assert draft.status_code == 201
    post_id = draft.json()["id"]
    assert draft.json()["status"] == "draft"

    assert api.get(f"/content/posts/{post_id}", headers=student).status_code == 404
    assert api.get("/content/posts", headers=student).json()["total"] == 0

    published = api.post(f"/content/posts/{post_id}/publish", headers=trainer)
    assert published.status_code == 200
    assert published.json()["published_at"] is not None

    listing = api.get("/content/posts", headers=student).json()
    assert [item["id"] for item in listing["items"]] == [post_id]
    detail = api.get(f"/content/posts/{post_id}", headers=student).json()
    assert detail["content"] == "Control the centre." and detail["can_edit"] is False

    notified = world.db.scalar(
        select(Notification).where(
            Notification.user_id == world.users["a"].id, Notification.notification_type == "post_published"
        )
    )
    assert notified is not None

    # Published posts must be unpublished or archived before deletion.
    assert api.delete(f"/content/posts/{post_id}", headers=trainer).status_code == 409
    assert api.post(f"/content/posts/{post_id}/archive", headers=trainer).status_code == 200
    assert api.get(f"/content/posts/{post_id}", headers=student).status_code == 404
    assert api.delete(f"/content/posts/{post_id}", headers=trainer).status_code == 204


def test_post_permissions(api, world):
    student = world.headers["a"]
    assert create_post(api, student).status_code == 403

    post_id = create_post(api, world.trainer_headers).json()["id"]
    api.post(f"/content/posts/{post_id}/publish", headers=world.trainer_headers)

    other_trainer_user = _user(world.db, "trainer", "Other Trainer")
    world.db.add(TrainerProfile(user_id=other_trainer_user.id))
    world.db.flush()
    other = auth_headers(other_trainer_user)

    assert api.patch(f"/content/posts/{post_id}", json={"title": "Hijacked"}, headers=other).status_code == 403
    assert api.patch(f"/content/posts/{post_id}", json={"title": "Hijacked"}, headers=student).status_code == 403

    admin = auth_headers(_user(world.db, "admin", "Admin"))
    edited = api.patch(f"/content/posts/{post_id}", json={"title": "Edited by admin"}, headers=admin)
    assert edited.status_code == 200 and edited.json()["title"] == "Edited by admin"

    # Another trainer's draft is invisible to them; admins see everything.
    draft_id = create_post(api, world.trainer_headers, title="Secret draft").json()["id"]
    assert api.get(f"/content/posts/{draft_id}", headers=other).status_code == 404
    assert api.get(f"/content/posts/{draft_id}", headers=admin).status_code == 200


def test_status_transitions(api, world):
    trainer = world.trainer_headers
    post_id = create_post(api, trainer).json()["id"]
    assert api.post(f"/content/posts/{post_id}/unpublish", headers=trainer).status_code == 409
    assert api.post(f"/content/posts/{post_id}/publish", headers=trainer).status_code == 200
    assert api.post(f"/content/posts/{post_id}/publish", headers=trainer).status_code == 409
    assert api.post(f"/content/posts/{post_id}/unpublish", headers=trainer).json()["status"] == "draft"


# --- Images ---------------------------------------------------------------------


def test_image_upload_and_photo_post(api, world, media_root):
    trainer = world.trainer_headers

    uploaded = upload(api, trainer)
    assert uploaded.status_code == 201
    url = uploaded.json()["url"]
    assert url.startswith("/media/") and url.endswith(".png")
    assert any(media_root.rglob("*.png"))

    served = api.get(url)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff"
    assert served.content == PNG

    photo = create_post(api, trainer, type="photo", title="Tournament day", image_url=url)
    assert photo.status_code == 201

    assert create_post(api, trainer, type="photo", title="No image").status_code == 422
    assert create_post(api, trainer, image_url="https://evil.example.com/x.png").status_code == 422
    assert create_post(api, trainer, image_url="/media/" + "0" * 32 + ".png").status_code == 422


def test_upload_validation(api, world):
    trainer = world.trainer_headers
    assert upload(api, trainer, SVG, "evil.svg").status_code == 422
    assert upload(api, trainer, b"GIF89a" + b"\x00" * 10, "fake.png").json()["mime_type"] == "image/gif"
    assert upload(api, trainer, b"", "empty.png").status_code == 422
    assert upload(api, trainer, b"\x89PNG\r\n\x1a\n" + b"\x00" * (settings.media_max_bytes + 1)).status_code == 422
    assert upload(api, world.headers["a"]).status_code == 403
    assert api.get("/media/../../etc/passwd").status_code == 404
    assert api.get("/media/" + "f" * 32 + ".png").status_code == 404


# --- Feedback ----------------------------------------------------------------------


def test_student_feedback_to_own_trainer(api, world):
    student = world.headers["a"]

    recipients = api.get("/feedback/recipients", headers=student).json()
    assert recipients == [{"id": str(world.trainer_user.id), "name": world.trainer_user.full_name}]

    sent = api.post(
        "/feedback",
        json={"to_user_id": str(world.trainer_user.id), "message": "Loved the pins lesson", "rating": 5, "category": "teaching"},
        headers=student,
    )
    assert sent.status_code == 201
    feedback_id = sent.json()["id"]
    assert sent.json()["can_review"] is False

    inbox = api.get("/feedback", params={"box": "inbox"}, headers=world.trainer_headers).json()
    assert [item["id"] for item in inbox["items"]] == [feedback_id]
    assert inbox["items"][0]["can_review"] is True

    assert api.post(f"/feedback/{feedback_id}/review", json={"response": "x"}, headers=student).status_code == 403
    assert api.get(f"/feedback/{feedback_id}", headers=world.headers["b"]).status_code == 404

    reviewed = api.post(f"/feedback/{feedback_id}/review", json={"response": "Thank you!"}, headers=world.trainer_headers)
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed" and reviewed.json()["response"] == "Thank you!"

    sent_box = api.get("/feedback", params={"box": "sent"}, headers=student).json()
    assert sent_box["items"][0]["status"] == "reviewed"
    types = set(world.db.scalars(select(Notification.notification_type)))
    assert {"feedback_received", "feedback_reviewed"} <= types


def test_student_cannot_write_to_other_trainers(api, world):
    other = _user(world.db, "trainer", "Stranger")
    world.db.add(TrainerProfile(user_id=other.id))
    world.db.flush()

    response = api.post("/feedback", json={"to_user_id": str(other.id), "message": "Hello there"}, headers=world.headers["a"])
    assert response.status_code == 422
    assert api.post("/feedback", json={"message": "No recipient"}, headers=world.headers["a"]).status_code == 422


def test_trainer_feedback_to_admins(api, world):
    admin_user = _user(world.db, "admin", "Admin")
    admin = auth_headers(admin_user)

    sent = api.post(
        "/feedback", json={"message": "Need more puzzle themes", "category": "platform"}, headers=world.trainer_headers
    )
    assert sent.status_code == 201
    assert sent.json()["audience"] == "admin" and sent.json()["to_name"] == "Academy admins"

    with_rating = api.post("/feedback", json={"message": "Rated", "rating": 4}, headers=world.trainer_headers)
    assert with_rating.status_code == 422

    inbox = api.get("/feedback", params={"box": "inbox"}, headers=admin).json()
    assert [item["id"] for item in inbox["items"]] == [sent.json()["id"]]

    assert api.post("/feedback", json={"message": "Admins do not send"}, headers=admin).status_code == 403
    assert api.get("/feedback", params={"box": "all"}, headers=world.trainer_headers).status_code == 403

    reviewed = api.post(f"/feedback/{sent.json()['id']}/review", json={}, headers=admin).json()
    assert reviewed["status"] == "reviewed" and reviewed["reviewer_name"] == "Admin"


def test_group_trainer_is_a_valid_recipient(api, world):
    group_trainer_user = _user(world.db, "trainer", "Group Coach")
    profile = TrainerProfile(user_id=group_trainer_user.id)
    world.db.add(profile)
    world.db.flush()
    world.group.trainer_id = profile.id
    world.db.flush()

    names = {item["name"] for item in api.get("/feedback/recipients", headers=world.headers["a"]).json()}
    assert names == {"Group Coach", world.trainer_user.full_name}
    assert world.db.scalar(select(StudentProfile.trainer_id).where(StudentProfile.id == world.students["a"].id)) == world.trainer.id
