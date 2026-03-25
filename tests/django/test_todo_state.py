
import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

from services.django_web.core.models import ChildTodo, ParentChild


@pytest.mark.django_db
def test_todo_state_transition_rules():
    child = User.objects.create_user(username="child_1", password="pass")
    todo = ChildTodo.objects.create(child=child, title="수학 숙제")

    todo.transition_to("doing")
    assert todo.status == "doing"

    todo.transition_to("done")
    assert todo.status == "done"

    with pytest.raises(ValueError):
        todo.transition_to("doing")


@pytest.mark.django_db
def test_parent_can_create_and_update_child_todo_via_api():
    parent = User.objects.create_user(username="parent_1", password="pass")
    child = User.objects.create_user(username="child_2", password="pass")
    ParentChild.objects.create(parent=parent, child=child)

    client = Client()
    client.force_login(parent)

    create_response = client.post(
        f"/api/children/{child.id}/todos",
        data=json.dumps({"title": "영어 단어 암기", "priority": 2}),
        content_type="application/json",
    )

    assert create_response.status_code == 201
    todo_id = create_response.json()["id"]

    patch_response = client.patch(
        f"/api/todos/{todo_id}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "done"


@pytest.mark.django_db
def test_parent_todo_create_rejects_invalid_due_date():
    parent = User.objects.create_user(username="parent_due", password="pass")
    child = User.objects.create_user(username="child_due", password="pass")
    ParentChild.objects.create(parent=parent, child=child)

    client = Client()
    client.force_login(parent)

    response = client.post(
        f"/api/children/{child.id}/todos",
        data=json.dumps({"title": "체크", "priority": 3, "due_date": "2026/03/30"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "due_date" in response.json()["error"]
