
from __future__ import annotations

import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

from services.django_web.core.models import AppRuntimeConfig, ParentChild


@pytest.mark.django_db
def test_api_chat_send_forwards_runtime_llm_config(monkeypatch):
    parent = User.objects.create_user(username="parent_llm", password="pass")
    child = User.objects.create_user(username="child_llm", password="pass")
    ParentChild.objects.create(parent=parent, child=child)

    AppRuntimeConfig.objects.update_or_create(
        key=AppRuntimeConfig.KEY_LLM_PROVIDER,
        defaults={"value": "ollama"},
    )
    AppRuntimeConfig.objects.update_or_create(
        key=AppRuntimeConfig.KEY_LLM_BASE_URL,
        defaults={"value": "http://ollama:11434"},
    )
    AppRuntimeConfig.objects.update_or_create(
        key=AppRuntimeConfig.KEY_OPENAI_MODEL,
        defaults={"value": "qwen2.5:7b"},
    )

    captured = {}

    def fake_call_fastapi_chat(payload):
        captured.update(payload)
        return {
            "reply_text": "로컬 모델 응답",
            "sentiment": "neutral",
            "topics": [],
            "suggested_todos": [],
        }

    monkeypatch.setattr("services.django_web.core.views.call_fastapi_chat", fake_call_fastapi_chat)

    client = Client()
    client.force_login(parent)
    response = client.post(
        "/api/chat/send",
        data=json.dumps({"child_id": child.id, "session_id": "s-local", "user_text": "테스트"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert captured["llm_config"]["provider"] == "ollama"
    assert captured["llm_config"]["model"] == "qwen2.5:7b"
    assert captured["llm_config"]["base_url"] == "http://ollama:11434"
