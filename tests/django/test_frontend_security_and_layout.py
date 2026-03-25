
from __future__ import annotations

import json

import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.mark.django_db
def test_base_uses_static_assets_without_inline_blocks():
    client = Client()
    response = client.get("/login")

    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert '<link rel="stylesheet"' in html
    assert 'src="/static/' in html
    assert "<style>" not in html


@pytest.mark.django_db
def test_api_chat_send_requires_csrf_token(monkeypatch):
    child = User.objects.create_user(username="child_csrf", password="pass")

    def fake_call_fastapi_chat(payload):
        return {
            "reply_text": "확인했어요.",
            "sentiment": "neutral",
            "topics": [],
            "suggested_todos": [],
        }

    monkeypatch.setattr("services.django_web.core.views.call_fastapi_chat", fake_call_fastapi_chat)

    client = Client(enforce_csrf_checks=True)
    client.force_login(child)
    response = client.post(
        "/api/chat/send",
        data=json.dumps({"session_id": "csrf-session", "child_id": child.id, "user_text": "테스트"}),
        content_type="application/json",
    )

    assert response.status_code == 403
