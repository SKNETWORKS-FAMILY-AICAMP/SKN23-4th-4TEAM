
from __future__ import annotations

from fastapi.testclient import TestClient

from services.fastapi_ai.app.main import app


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_chat_respond_uses_ollama_when_llm_config_provider_is_ollama(monkeypatch):
    client = TestClient(app)

    def fake_post(url, json, timeout):
        assert url == "http://ollama:11434/api/generate"
        assert json["model"] == "qwen3:8b"
        return _FakeResponse({"response": "로컬 LLM 답변"})

    monkeypatch.setattr("services.fastapi_ai.app.main.requests.post", fake_post)

    response = client.post(
        "/v1/chat/respond",
        json={
            "session_id": "s-local",
            "child_id": 1,
            "user_text": "오늘 할일 알려줘",
            "history": [{"role": "child", "content": "안녕"}],
            "child_profile": {"grade": "초5", "interests": ["축구"], "guidance": "숙제 우선"},
            "llm_config": {
                "provider": "ollama",
                "model": "qwen3:8b",
                "base_url": "http://ollama:11434",
                "api_key": "",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["reply_text"] == "로컬 LLM 답변"
