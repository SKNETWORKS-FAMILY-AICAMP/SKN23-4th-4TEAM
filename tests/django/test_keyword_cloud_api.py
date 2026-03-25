
import pytest
from django.contrib.auth.models import User
from django.test import Client

from services.django_web.core.models import KeywordObservation, ParentChild


@pytest.mark.django_db
def test_keyword_cloud_api_returns_remote_summary_and_local_cloud(monkeypatch):
    parent = User.objects.create_user(username="parent_cloud", password="pass")
    child = User.objects.create_user(username="child_cloud", password="pass")
    ParentChild.objects.create(parent=parent, child=child)

    KeywordObservation.objects.create(child=child, term="숙제", weight=1.0, polarity="positive")
    KeywordObservation.objects.create(child=child, term="게임", weight=0.7, polarity="negative")

    def fake_keywords(child_id, texts, window_days):
        return {
            "top_keywords": [{"term": "숙제", "score": 1.0, "polarity": "positive"}],
            "summary": {"positive_ratio": 1.0, "neutral_ratio": 0.0, "negative_ratio": 0.0},
        }

    monkeypatch.setattr("services.django_web.core.views.call_fastapi_keywords", fake_keywords)

    client = Client()
    client.force_login(parent)
    response = client.get(f"/api/children/{child.id}/keyword-cloud?days=7")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["positive_ratio"] == 1.0
    assert len(payload["keyword_cloud"]) >= 1
