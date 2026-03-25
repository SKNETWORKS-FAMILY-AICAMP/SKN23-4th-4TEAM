
from fastapi.testclient import TestClient

from services.fastapi_ai.app.main import app


def test_chat_respond_contract_fields_exist():
    client = TestClient(app)
    response = client.post(
        "/v1/chat/respond",
        json={
            "session_id": "s-1",
            "child_id": 1,
            "user_text": "오늘 숙제를 해서 뿌듯했어요",
            "history": [{"role": "child", "content": "안녕"}],
            "child_profile": {"grade": "초5", "interests": ["축구"], "guidance": "숙제 우선"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"reply_text", "sentiment", "topics", "suggested_todos"}
    assert data["sentiment"] in {"positive", "neutral", "negative"}
    assert isinstance(data["topics"], list)
    assert isinstance(data["suggested_todos"], list)
