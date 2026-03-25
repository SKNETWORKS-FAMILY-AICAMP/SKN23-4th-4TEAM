
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

TOKEN_RE = re.compile(r"[A-Za-z가-힣0-9]{2,}")

STOPWORDS = {
    "오늘", "어제", "그리고", "하지만", "그래서", "정말", "조금", "조금만",
    "너무", "이번", "저녁", "아침", "점심", "그냥", "있어요", "했어요", "했다",
    "하면서", "에게", "에서", "으로", "하고", "대한", "같은", "이런", "저런",
}

POSITIVE_TERMS = {
    "좋아", "좋아요", "행복", "뿌듯", "기쁨", "재밌", "신남", "만족", "즐거", "평온",
}

NEGATIVE_TERMS = {
    "속상", "불안", "짜증", "화남", "힘들", "어려", "걱정", "우울", "피곤", "슬픔",
}

KOREAN_PARTICLE_SUFFIXES = (
    "으로", "에서", "에게", "으로", "랑", "과", "와",
    "을", "를", "이", "가", "은", "는", "도",
)


def _normalize_token(token: str) -> str:
    cleaned = token.lower()
    for suffix in KOREAN_PARTICLE_SUFFIXES:
        if cleaned.endswith(suffix) and len(cleaned) > len(suffix) + 1:
            cleaned = cleaned[: -len(suffix)]
            break
    return cleaned


def tokenize(text: str) -> list[str]:
    return [_normalize_token(token) for token in TOKEN_RE.findall(text or "")]


def _token_polarity(token: str) -> str:
    if any(key in token for key in POSITIVE_TERMS):
        return "positive"
    if any(key in token for key in NEGATIVE_TERMS):
        return "negative"
    return "neutral"


def classify_sentiment(text: str) -> str:
    tokens = tokenize(text)
    pos = sum(1 for token in tokens if _token_polarity(token) == "positive")
    neg = sum(1 for token in tokens if _token_polarity(token) == "negative")
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def sentiment_summary(texts: Iterable[str]) -> dict[str, float]:
    labels = [classify_sentiment(text) for text in texts]
    total = len(labels) or 1
    return {
        "positive_ratio": round(labels.count("positive") / total, 4),
        "neutral_ratio": round(labels.count("neutral") / total, 4),
        "negative_ratio": round(labels.count("negative") / total, 4),
    }


def extract_keywords(texts: Iterable[str], top_k: int = 20) -> list[dict[str, object]]:
    counts: Counter[str] = Counter()
    for text in texts:
        for token in tokenize(text):
            if token in STOPWORDS:
                continue
            counts[token] += 1

    if not counts:
        return []

    max_count = max(counts.values())
    keywords: list[dict[str, object]] = []
    for term, count in counts.most_common(top_k):
        keywords.append(
            {
                "term": term,
                "score": round(count / max_count, 4),
                "polarity": _token_polarity(term),
            }
        )
    return keywords


def build_suggested_todos(keywords: list[dict[str, object]]) -> list[str]:
    suggestions: list[str] = []
    terms = [str(item["term"]) for item in keywords[:5]]
    if "숙제" in terms:
        suggestions.append("숙제 20분 집중하기")
    if any(term in terms for term in ["게임", "유튜브", "핸드폰"]):
        suggestions.append("미디어 사용 시간 30분 제한")
    if any(item.get("polarity") == "negative" for item in keywords[:5]):
        suggestions.append("오늘 기분 메모 3줄 작성")
    if not suggestions:
        suggestions.append("오늘 할 일 1개 완료 체크")
    return suggestions[:3]
