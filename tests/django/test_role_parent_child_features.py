
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from services.django_web.core.models import ChildChatMessage, ChildProfile, ChildTodo, ParentChild


@pytest.mark.django_db
def test_base_nav_shows_only_role_relevant_links():
    admin = User.objects.create_user(username="admin_r", password="pass", is_staff=True, is_superuser=True)
    parent = User.objects.create_user(username="parent_r", password="pass")
    child = User.objects.create_user(username="child_r", password="pass")
    ParentChild.objects.create(parent=parent, child=child)
    ChildProfile.objects.create(child=child)

    client = Client()

    client.force_login(admin)
    admin_html = client.get("/admin").content.decode("utf-8")
    assert 'href="/admin"' in admin_html
    assert 'href="/parent"' not in admin_html
    assert 'href="/child/chat"' not in admin_html

    client.force_login(parent)
    parent_html = client.get("/parent").content.decode("utf-8")
    assert 'href="/parent"' in parent_html
    assert 'href="/admin"' not in parent_html
    assert 'href="/child/chat"' not in parent_html

    client.force_login(child)
    child_html = client.get("/child/chat").content.decode("utf-8")
    assert 'href="/child/chat"' in child_html
    assert 'href="/admin"' not in child_html
    assert 'href="/parent"' not in child_html


@pytest.mark.django_db
def test_parent_can_create_only_owned_child():
    parent = User.objects.create_user(username="parent_owner", password="pass")
    other_parent = User.objects.create_user(username="parent_other", password="pass")

    client = Client()
    client.force_login(parent)

    response = client.post(
        "/parent/children/create",
        data={
            "username": "child_new",
            "password": "1234",
            "grade": "초4",
            "interests": "축구,과학",
            "guidance": "숙제 먼저",
        },
    )

    assert response.status_code == 302
    child = User.objects.get(username="child_new")
    assert ParentChild.objects.filter(parent=parent, child=child).exists()
    assert not ParentChild.objects.filter(parent=other_parent, child=child).exists()


@pytest.mark.django_db
def test_parent_child_detail_filters_messages_by_chat_date():
    parent = User.objects.create_user(username="parent_filter", password="pass")
    child = User.objects.create_user(username="child_filter", password="pass")
    ParentChild.objects.create(parent=parent, child=child)

    now = timezone.now()
    old_day = now - timedelta(days=1)
    ChildChatMessage.objects.create(child=child, session_id="s", role="child", content="오늘 대화", created_at=now)
    ChildChatMessage.objects.create(child=child, session_id="s", role="child", content="어제 대화", created_at=old_day)

    client = Client()
    client.force_login(parent)

    day = now.date().isoformat()
    response = client.get(f"/parent/child/{child.id}?chat_date={day}")

    html = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "오늘 대화" in html
    assert "어제 대화" not in html
    assert "ChildChatMessage object" not in html


@pytest.mark.django_db
def test_child_chat_page_contains_todo_popup_list():
    child = User.objects.create_user(username="child_popup", password="pass")
    ChildProfile.objects.create(child=child)
    ChildTodo.objects.create(child=child, title="수학 2쪽", status=ChildTodo.STATUS_TODO)

    client = Client()
    client.force_login(child)

    response = client.get("/child/chat")

    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'id="child-todo-modal"' in html
    assert "수학 2쪽" in html


@pytest.mark.django_db
def test_todo_done_marks_calendar_date():
    parent = User.objects.create_user(username="parent_cal", password="pass")
    child = User.objects.create_user(username="child_cal", password="pass")
    ParentChild.objects.create(parent=parent, child=child)

    todo = ChildTodo.objects.create(child=child, title="완료 체크")
    todo.transition_to(ChildTodo.STATUS_DONE)
    todo.refresh_from_db()

    assert todo.done_at is not None

    client = Client()
    client.force_login(parent)
    response = client.get(f"/parent/child/{child.id}")

    html = response.content.decode("utf-8")
    assert todo.done_at.date().isoformat() in html
