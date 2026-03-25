
from fastapi.testclient import TestClient

from services.fastapi_ai.app.main import app
from services.fastapi_ai.app.keyword_engine import extract_keywords


def test_extract_keywords_filters_stopwords_and_scores_terms():
    texts = [
        "오늘 학교 숙제를 다 했고 기분이 좋아요",
        "숙제랑 독서를 끝내서 뿌듯해요",
        "게임은 조금만 하고 숙제를 먼저 했어요",
    ]

    result = extract_keywords(texts=texts, top_k=5)

    assert result[0]["term"] == "숙제"
    assert result[0]["score"] > 0
    assert all(item["term"] not in {"오늘", "조금만"} for item in result)


def test_keywords_extract_endpoint_returns_sentiment_summary_and_topics():
    client = TestClient(app)
    payload = {
        "child_id": 7,
        "window_days": 7,
        "texts": [
            "오늘은 친구랑 놀아서 정말 좋아요",
            "수학 숙제는 어려워서 조금 속상했어요",
            "저녁에는 기분이 평온했어요",
        ],
    }

    response = client.post("/v1/keywords/extract", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "top_keywords" in data
    assert "summary" in data
    assert set(data["summary"].keys()) == {"positive_ratio", "neutral_ratio", "negative_ratio"}
    assert len(data["top_keywords"]) > 0
