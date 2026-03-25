
from __future__ import annotations

import os

import requests
from pydantic import BaseModel, Field
from fastapi import FastAPI

from services.fastapi_ai.app.keyword_engine import (
    build_suggested_todos,
    classify_sentiment,
    extract_keywords,
    sentiment_summary,
)


DEFAULT_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "rule")
DEFAULT_LLM_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")


class HistoryItem(BaseModel):
    role: str = Field(pattern="^(child|ai)$")
    content: str


class ChildProfile(BaseModel):
    grade: str = ""
    interests: list[str] = Field(default_factory=list)
    guidance: str = ""


class LlmConfig(BaseModel):
    provider: str = ""
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.4


class ChatRespondRequest(BaseModel):
    session_id: str
    child_id: int
    user_text: str
    history: list[HistoryItem] = Field(default_factory=list)
    child_profile: ChildProfile = Field(default_factory=ChildProfile)
    llm_config: LlmConfig = Field(default_factory=LlmConfig)


class KeywordExtractRequest(BaseModel):
    child_id: int
    window_days: int = 7
    texts: list[str] = Field(default_factory=list)


app = FastAPI(title="YouOnlyTalkOnce AI Service", version="1.1.0")


def _sanitize(value: str) -> str:
    return (value or "").strip()


def _active_llm_config(payload: ChatRespondRequest) -> dict[str, str | float]:
    provider = _sanitize(payload.llm_config.provider) or _sanitize(DEFAULT_LLM_PROVIDER) or "rule"
    model = _sanitize(payload.llm_config.model) or _sanitize(DEFAULT_LLM_MODEL) or "gpt-4o-mini"
    api_key = _sanitize(payload.llm_config.api_key) or _sanitize(DEFAULT_LLM_API_KEY)
    base_url = _sanitize(payload.llm_config.base_url) or _sanitize(DEFAULT_LLM_BASE_URL)
    temperature = float(payload.llm_config.temperature or 0.4)
    return {
        "provider": provider.lower(),
        "model": model,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": max(0.0, min(1.0, temperature)),
    }


def _rule_based_reply(payload: ChatRespondRequest) -> str:
    guidance = payload.child_profile.guidance.strip()
    guidance_sentence = f" 보호자 가이드: {guidance}" if guidance else ""
    return (
        "오늘 대화를 잘 기록했어요. 지금 이야기한 내용을 기준으로 "
        "작은 할 일을 하나씩 완료해보면 좋아요."
        f"{guidance_sentence}"
    ).strip()


def _history_text(payload: ChatRespondRequest) -> str:
    if not payload.history:
        return "이전 대화 없음"
    lines = [f"{item.role}: {item.content}" for item in payload.history[-8:]]
    return "\n".join(lines)


def _build_messages(payload: ChatRespondRequest) -> list[dict[str, str]]:
    profile = payload.child_profile
    interests = ", ".join(profile.interests) if profile.interests else "-"
    guidance = profile.guidance.strip() or "-"
    user_prompt = (
        "[도메인]\n"
        "자녀 관리 코치\n\n"
        "[자녀 정보]\n"
        f"학년: {profile.grade or '-'}\n"
        f"관심사: {interests}\n"
        f"가이드: {guidance}\n\n"
        "[최근 대화]\n"
        f"{_history_text(payload)}\n\n"
        "[현재 입력]\n"
        f"{payload.user_text}\n\n"
        "[출력 규칙]\n"
        "2~3문장으로 짧게 답하고, 할일 1~2개를 제안하세요."
    )
    return [
        {
            "role": "system",
            "content": "너는 치료/진단 용어를 쓰지 않는 자녀 관리 도우미다.",
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]


def _chat_openai_compatible(
    *,
    messages: list[dict[str, str]],
    model: str,
    base_url: str,
    api_key: str,
    temperature: float,
) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
        },
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices", [])
    if not choices:
        raise ValueError("empty choices")
    message = choices[0].get("message", {})
    content = str(message.get("content", "")).strip()
    if not content:
        raise ValueError("empty content")
    return content


def _chat_ollama(*, prompt: str, model: str, base_url: str, temperature: float) -> str:
    response = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    content = str(payload.get("response", "")).strip()
    if not content:
        raise ValueError("empty ollama response")
    return content


def _generate_reply(payload: ChatRespondRequest, llm: dict[str, str | float]) -> str:
    provider = str(llm["provider"])
    model = str(llm["model"])
    base_url = str(llm["base_url"])
    api_key = str(llm["api_key"])
    temperature = float(llm["temperature"])

    if provider == "rule":
        return _rule_based_reply(payload)

    try:
        if provider == "ollama":
            endpoint = base_url or "http://localhost:11434"
            return _chat_ollama(
                prompt=_build_messages(payload)[-1]["content"],
                model=model,
                base_url=endpoint,
                temperature=temperature,
            )

        if provider == "openai":
            endpoint = base_url or "https://api.openai.com/v1"
            return _chat_openai_compatible(
                messages=_build_messages(payload),
                model=model,
                base_url=endpoint,
                api_key=api_key,
                temperature=temperature,
            )

        if provider in {"openai_compatible", "local_openai"}:
            endpoint = base_url or "http://localhost:8000/v1"
            return _chat_openai_compatible(
                messages=_build_messages(payload),
                model=model,
                base_url=endpoint,
                api_key=api_key,
                temperature=temperature,
            )
    except Exception:
        return _rule_based_reply(payload)

    return _rule_based_reply(payload)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/v1/keywords/extract")
def keywords_extract(payload: KeywordExtractRequest) -> dict[str, object]:
    keywords = extract_keywords(payload.texts, top_k=20)
    summary = sentiment_summary(payload.texts)
    return {
        "child_id": payload.child_id,
        "window_days": payload.window_days,
        "top_keywords": keywords,
        "summary": summary,
    }


@app.post("/v1/chat/respond")
def chat_respond(payload: ChatRespondRequest) -> dict[str, object]:
    texts = [payload.user_text]
    keywords = extract_keywords(texts, top_k=10)
    sentiment = classify_sentiment(payload.user_text)
    todos = build_suggested_todos(keywords)
    llm = _active_llm_config(payload)
    reply = _generate_reply(payload, llm)

    return {
        "reply_text": reply,
        "sentiment": sentiment,
        "topics": [
            {
                "term": item["term"],
                "weight": item["score"],
                "polarity": item["polarity"],
            }
            for item in keywords
        ],
        "suggested_todos": todos,
    }
