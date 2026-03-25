
import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

from services.django_web.core.models import ChildChatMessage, KeywordObservation, ParentChild


@pytest.mark.django_db
def test_api_chat_send_persists_messages_and_keyword_observation(monkeypatch):
    parent = User.objects.create_user(username="parent_x", password="pass")
    child = User.objects.create_user(username="child_x", password="pass")
    ParentChild.objects.create(parent=parent, child=child)

    def fake_call_fastapi_chat(payload):
        return {
            "reply_text": "좋은 시작이에요. 숙제 20분 집중해봐요.",
            "sentiment": "positive",
            "topics": [{"term": "숙제", "weight": 1.0, "polarity": "positive"}],
            "suggested_todos": ["숙제 20분 집중하기"],
        }

    monkeypatch.setattr("services.django_web.core.views.call_fastapi_chat", fake_call_fastapi_chat)

    client = Client()
    client.force_login(parent)
    response = client.post(
        "/api/chat/send",
        data=json.dumps({"child_id": child.id, "session_id": "session-1", "user_text": "오늘 숙제를 했어요"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert "reply_text" in body
    assert body["sentiment"] == "positive"

    assert ChildChatMessage.objects.filter(child=child).count() == 2
    assert KeywordObservation.objects.filter(child=child, term="숙제").exists()
