
from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.test import Client

from services.django_web.core.models import ChildProfile, ParentChild


@pytest.mark.django_db
def test_base_header_uses_post_logout_form():
    child = User.objects.create_user(username="child_logout", password="pass")

    client = Client()
    client.force_login(child)

    response = client.get("/child/chat")

    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'action="/logout"' in html
    assert 'method="post"' in html
    assert 'href="/logout"' not in html


@pytest.mark.django_db
def test_admin_can_create_parent_and_child_with_mapping():
    admin = User.objects.create_user(username="admin_manage", password="pass", is_staff=True, is_superuser=True)

    client = Client()
    client.force_login(admin)

    create_parent = client.post(
        "/admin/users/parent",
        data={
            "username": "parent_alpha",
            "password": "Parent1234!",
        },
    )
    assert create_parent.status_code == 302

    parent = User.objects.get(username="parent_alpha")

    create_child = client.post(
        "/admin/users/child",
        data={
            "username": "child_alpha",
            "password": "Child1234!",
            "grade": "초5",
            "interests": "축구,과학",
            "guidance": "숙제 먼저",
            "parent_id": str(parent.id),
            "consent_given": "on",
        },
    )
    assert create_child.status_code == 302

    child = User.objects.get(username="child_alpha")
    assert ParentChild.objects.filter(parent=parent, child=child).exists()

    profile = ChildProfile.objects.get(child=child)
    assert profile.grade == "초5"


@pytest.mark.django_db
def test_admin_rag_reindex_endpoint_exists():
    admin = User.objects.create_user(username="admin_rag", password="pass", is_staff=True, is_superuser=True)

    client = Client()
    client.force_login(admin)

    response = client.get("/rag/reindex")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/admin/rag/index")
