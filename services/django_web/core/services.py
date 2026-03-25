
from __future__ import annotations

import os
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import requests
from django.contrib.auth.models import User
from django.db.models import Count, Q, QuerySet
from django.utils import timezone
from pypdf import PdfReader

from .models import (
    AppRuntimeConfig,
    ChildChatMessage,
    ChildConsent,
    ChildMessageAlert,
    KeywordDailyStat,
    KeywordObservation,
    RagChunk,
    RagDocument,
)


FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8001")
FASTAPI_TIMEOUT_SECONDS = float(os.getenv("FASTAPI_TIMEOUT_SECONDS", "10"))
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_SYSTEM_PROMPT = (
    "너는 자녀 관리 도우미 AI 운영 정책 관리자다. "
    "치료/임상 판단 문구를 사용하지 않고 일상 관리 중심으로 응답한다."
)
DEFAULT_USER_PROMPT_TEMPLATE = (
    "[INPUT] {user_text}\n"
    "[CHILD_PROFILE] {child_profile}\n"
    "[HISTORY] {history}\n"
    "관리 가능한 다음 행동을 제안하라."
)
DEFAULT_CHILD_SYSTEM_PROMPT = (
    "너는 자녀와 대화하는 학습/생활 관리 도우미다. "
    "간단하고 안전한 표현으로 답변한다."
)
DEFAULT_CHILD_USER_PROMPT_TEMPLATE = (
    "[INPUT] {user_text}\n"
    "[GUIDANCE] {child_guidance}\n"
    "[OUTPUT] 2~3문장 공감 + 1~2개 할 일 제안"
)

RUNTIME_KEY_ORDER = (
    AppRuntimeConfig.KEY_LLM_PROVIDER,
    AppRuntimeConfig.KEY_LLM_BASE_URL,
    AppRuntimeConfig.KEY_OPENAI_MODEL,
    AppRuntimeConfig.KEY_OPENAI_API_KEY,
    AppRuntimeConfig.KEY_SYSTEM_PROMPT,
    AppRuntimeConfig.KEY_USER_PROMPT_TEMPLATE,
    AppRuntimeConfig.KEY_CHILD_SYSTEM_PROMPT,
    AppRuntimeConfig.KEY_CHILD_USER_PROMPT_TEMPLATE,
)
RUNTIME_DEFAULTS = {
    AppRuntimeConfig.KEY_LLM_PROVIDER: os.getenv("LLM_PROVIDER", "rule"),
    AppRuntimeConfig.KEY_LLM_BASE_URL: os.getenv("LLM_BASE_URL", ""),
    AppRuntimeConfig.KEY_OPENAI_MODEL: os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    AppRuntimeConfig.KEY_OPENAI_API_KEY: os.getenv("OPENAI_API_KEY", ""),
    AppRuntimeConfig.KEY_SYSTEM_PROMPT: DEFAULT_SYSTEM_PROMPT,
    AppRuntimeConfig.KEY_USER_PROMPT_TEMPLATE: DEFAULT_USER_PROMPT_TEMPLATE,
    AppRuntimeConfig.KEY_CHILD_SYSTEM_PROMPT: DEFAULT_CHILD_SYSTEM_PROMPT,
    AppRuntimeConfig.KEY_CHILD_USER_PROMPT_TEMPLATE: DEFAULT_CHILD_USER_PROMPT_TEMPLATE,
}

CONSENT_VERSION = "v1"
CONSENT_TEXT = "보호자는 자녀 관리 AI 도우미 사용 목적과 저장 범위를 확인하고 동의합니다."

SUPPORTED_DOC_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}


class _PromptProbeDict(dict):
    def __missing__(self, key: str) -> str:
        return f"<{key}>"


def call_fastapi_chat(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{FASTAPI_BASE_URL}/v1/chat/respond",
        json=payload,
        timeout=FASTAPI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def call_fastapi_keywords(child_id: int, texts: list[str], window_days: int) -> dict[str, Any]:
    response = requests.post(
        f"{FASTAPI_BASE_URL}/v1/keywords/extract",
        json={"child_id": child_id, "window_days": window_days, "texts": texts},
        timeout=FASTAPI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def sync_keyword_observations(
    *,
    child_id: int,
    message: ChildChatMessage,
    topics: list[dict[str, Any]],
    sentiment: str,
) -> None:
    for topic in topics:
        KeywordObservation.objects.create(
            child_id=child_id,
            message=message,
            term=str(topic.get("term", "")).strip()[:128],
            weight=float(topic.get("weight", 0.0) or 0.0),
            polarity=str(topic.get("polarity", "neutral") or "neutral"),
        )

    today = timezone.localdate()
    stat, _ = KeywordDailyStat.objects.get_or_create(child_id=child_id, stat_date=today)
    if sentiment == "positive":
        stat.positive_count += 1
    elif sentiment == "negative":
        stat.negative_count += 1
    else:
        stat.neutral_count += 1
    stat.save(update_fields=["positive_count", "neutral_count", "negative_count", "updated_at"])


def build_keyword_cloud(child_id: int, days: int = 7) -> list[dict[str, Any]]:
    days = max(1, min(30, int(days)))
    cutoff = timezone.now() - timedelta(days=days)
    rows: QuerySet[KeywordObservation] = KeywordObservation.objects.filter(
        child_id=child_id,
        observed_at__gte=cutoff,
    )

    score_counter: Counter[str] = Counter()
    polarity_counter: dict[str, Counter[str]] = {}

    for row in rows.iterator():
        score_counter[row.term] += float(row.weight)
        if row.term not in polarity_counter:
            polarity_counter[row.term] = Counter()
        polarity_counter[row.term][row.polarity] += 1

    if not score_counter:
        return []

    max_score = max(score_counter.values()) or 1.0
    cloud = []
    for term, score in score_counter.most_common(30):
        polarities = polarity_counter.get(term, Counter())
        dominant = polarities.most_common(1)[0][0] if polarities else "neutral"
        cloud.append(
            {
                "term": term,
                "score": round(score, 4),
                "weight": round(score / max_score, 4),
                "polarity": dominant,
            }
        )
    return cloud


def create_sentiment_alert(*, child_id: int, message: ChildChatMessage, sentiment: str) -> ChildMessageAlert | None:
    if sentiment != "negative":
        return None

    alert, _ = ChildMessageAlert.objects.get_or_create(
        message=message,
        defaults={
            "child_id": child_id,
            "reason": "negative_sentiment",
            "score": 1.0,
            "status": ChildMessageAlert.STATUS_OPEN,
        },
    )
    return alert


def list_open_alerts(limit: int = 20) -> QuerySet[ChildMessageAlert]:
    safe_limit = max(1, min(200, int(limit)))
    return (
        ChildMessageAlert.objects.filter(status=ChildMessageAlert.STATUS_OPEN)
        .select_related("child", "message")
        .order_by("-id")[:safe_limit]
    )


def resolve_alert(alert_id: int, actor: User) -> bool:
    updated = ChildMessageAlert.objects.filter(
        id=alert_id,
        status=ChildMessageAlert.STATUS_OPEN,
    ).update(
        status=ChildMessageAlert.STATUS_RESOLVED,
        resolved_at=timezone.now(),
        resolved_by=actor,
    )
    return updated > 0


def mask_api_key(value: str) -> str:
    key = (value or "").strip()
    if not key:
        return "-"
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


def _validate_prompt_template(template: str, required_tokens: tuple[str, ...]) -> tuple[bool, str]:
    cleaned = (template or "").strip()
    if not cleaned:
        return False, "프롬프트는 비워둘 수 없습니다."

    missing_tokens = [token for token in required_tokens if token not in cleaned]
    if missing_tokens:
        return False, f"필수 토큰 누락: {', '.join(missing_tokens)}"

    probe = _PromptProbeDict(
        user_text="USER",
        child_profile="PROFILE",
        history="HISTORY",
        child_guidance="GUIDANCE",
        session_meta="META",
    )
    try:
        cleaned.format_map(probe)
    except (ValueError, KeyError) as exc:
        return False, f"프롬프트 템플릿 형식 오류: {exc}"
    return True, ""


def validate_prompt_template(template: str) -> tuple[bool, str]:
    return _validate_prompt_template(template, required_tokens=("{user_text}",))


def validate_child_prompt_template(template: str) -> tuple[bool, str]:
    return _validate_prompt_template(template, required_tokens=("{user_text}", "{child_guidance}"))


def get_runtime_config() -> dict[str, str]:
    values = dict(RUNTIME_DEFAULTS)
    rows = AppRuntimeConfig.objects.filter(key__in=RUNTIME_KEY_ORDER)
    for row in rows:
        values[row.key] = row.value
    return values


def get_runtime_config_view() -> dict[str, str]:
    values = get_runtime_config()
    latest = AppRuntimeConfig.objects.select_related("updated_by").order_by("-updated_at").first()
    return {
        **values,
        "openai_api_key_masked": mask_api_key(values.get(AppRuntimeConfig.KEY_OPENAI_API_KEY, "")),
        "last_updated_at": latest.updated_at.strftime("%Y-%m-%d %H:%M") if latest else "-",
        "last_updated_by": latest.updated_by.username if latest and latest.updated_by else "-",
    }


def set_runtime_config(updates: dict[str, str], updated_by: User | None = None) -> None:
    if not updates:
        return

    for key, value in updates.items():
        if key not in RUNTIME_KEY_ORDER:
            continue
        AppRuntimeConfig.objects.update_or_create(
            key=key,
            defaults={"value": (value or "").strip(), "updated_by": updated_by},
        )


def _list_models_openai_compatible(*, base_url: str, api_key: str) -> list[str]:
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    response = requests.get(
        f"{base_url.rstrip('/')}/models",
        headers=headers,
        timeout=6,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data", [])
    names = [item.get("id", "") for item in rows if isinstance(item, dict)]
    return [item for item in names if item]


def _list_models_ollama(*, base_url: str) -> list[str]:
    response = requests.get(
        f"{base_url.rstrip('/')}/api/tags",
        timeout=6,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("models", [])
    names = [item.get("name", "") for item in rows if isinstance(item, dict)]
    return [item for item in names if item]


def list_available_models(*, provider: str, base_url: str, api_key: str) -> list[str]:
    fallback = [
        get_runtime_config().get(AppRuntimeConfig.KEY_OPENAI_MODEL, "gpt-4o-mini"),
        "gpt-4o-mini",
        "gpt-4.1-mini",
        "gpt-4o",
    ]
    merged = [item for item in fallback if item]

    provider_name = (provider or "rule").strip().lower()
    endpoint = (base_url or "").strip()
    key = (api_key or "").strip()

    try:
        if provider_name == "openai":
            openai_base = endpoint or "https://api.openai.com/v1"
            merged.extend(_list_models_openai_compatible(base_url=openai_base, api_key=key))
        elif provider_name in {"openai_compatible", "local_openai"}:
            openai_base = endpoint or "http://localhost:8000/v1"
            merged.extend(_list_models_openai_compatible(base_url=openai_base, api_key=key))
        elif provider_name == "ollama":
            ollama_base = endpoint or "http://localhost:11434"
            merged.extend(_list_models_ollama(base_url=ollama_base))
        else:
            if key:
                merged.extend(_list_models_openai_compatible(base_url="https://api.openai.com/v1", api_key=key))
            if endpoint:
                try:
                    merged.extend(_list_models_ollama(base_url=endpoint))
                except Exception:
                    merged.extend(_list_models_openai_compatible(base_url=endpoint, api_key=key))
    except Exception:
        pass

    return list(dict.fromkeys(item for item in merged if item))


def ensure_child_consent_row(child_id: int, default_given: bool = True) -> ChildConsent:
    now = timezone.now()
    defaults: dict[str, Any] = {
        "consent_given": bool(default_given),
        "consent_version": CONSENT_VERSION,
        "consent_text": CONSENT_TEXT,
    }
    if default_given:
        defaults["agreed_at"] = now

    consent, created = ChildConsent.objects.get_or_create(child_id=child_id, defaults=defaults)
    if created:
        return consent

    changed = False
    if not consent.consent_text:
        consent.consent_text = CONSENT_TEXT
        changed = True
    if not consent.consent_version:
        consent.consent_version = CONSENT_VERSION
        changed = True
    if changed:
        consent.save(update_fields=["consent_text", "consent_version", "updated_at"])
    return consent


def has_child_consent(child_id: int) -> bool:
    consent = ensure_child_consent_row(child_id, default_given=True)
    return bool(consent.consent_given)


def set_child_consent(*, child_id: int, consent_given: bool, updated_by: User | None) -> ChildConsent:
    consent = ensure_child_consent_row(child_id, default_given=True)
    now = timezone.now()

    consent.consent_given = bool(consent_given)
    consent.updated_by = updated_by
    consent.consent_version = CONSENT_VERSION
    consent.consent_text = CONSENT_TEXT
    if consent_given:
        consent.agreed_at = now
        consent.revoked_at = None
    else:
        consent.revoked_at = now

    consent.save(
        update_fields=[
            "consent_given",
            "consent_version",
            "consent_text",
            "agreed_at",
            "revoked_at",
            "updated_by",
            "updated_at",
        ]
    )
    return consent


def list_child_consents() -> list[dict[str, Any]]:
    children = (
        User.objects.filter(Q(parents__isnull=False) | Q(child_profile__isnull=False))
        .distinct()
        .order_by("username")
    )

    rows: list[dict[str, Any]] = []
    for child in children:
        consent = ensure_child_consent_row(child.id, default_given=True)
        rows.append(
            {
                "child_id": child.id,
                "username": child.username,
                "consent_given": consent.consent_given,
                "consent_version": consent.consent_version,
                "agreed_at": consent.agreed_at,
                "revoked_at": consent.revoked_at,
                "updated_at": consent.updated_at,
            }
        )
    return rows


def get_upload_source_dir() -> Path:
    return PROJECT_ROOT / "data" / "rag_sources"


def get_fallback_source_dir() -> Path:
    return PROJECT_ROOT / "data" / "assets"


def ensure_upload_source_dir() -> Path:
    upload_dir = get_upload_source_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def list_document_paths(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        return []
    docs = [path for path in source_dir.iterdir() if path.suffix.lower() in SUPPORTED_DOC_SUFFIXES]
    return sorted(docs, key=lambda item: item.name.lower())


def extract_text_from_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def extract_text_from_docx(path: Path) -> str:
    try:
        with ZipFile(path, "r") as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, OSError, ValueError):
        return ""

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return ""

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        tokens = [node.text for node in paragraph.findall(".//w:t", ns) if node.text]
        if tokens:
            paragraphs.append("".join(tokens))
    return "\n".join(paragraphs)


def extract_text_from_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix == ".docx":
        return extract_text_from_docx(path)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def should_preprocess(text: str) -> bool:
    if not text:
        return False
    return (text.count("\n") / max(1, len(text))) > 0.01


def preprocess_text(text: str) -> str:
    normalized = text.replace("-\n", "")
    normalized = normalized.replace("\n", " ")
    return " ".join(normalized.split())


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 120) -> list[str]:
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(length, start + chunk_size)
        chunks.append(text[start:end])
        start = max(0, end - overlap)
        if end == length:
            break
    return chunks


def reindex_documents() -> dict[str, Any]:
    upload_dir = ensure_upload_source_dir()
    source_mode = "upload"
    source_dir = upload_dir

    doc_paths = list_document_paths(upload_dir)
    if not doc_paths:
        fallback_dir = get_fallback_source_dir()
        doc_paths = list_document_paths(fallback_dir)
        source_mode = "fallback"
        source_dir = fallback_dir

    if not doc_paths:
        return {
            "count": 0,
            "message": "색인할 문서를 찾지 못했습니다.",
            "source_mode": source_mode,
            "source_dir": str(source_dir),
            "total_documents": 0,
            "indexed_documents": 0,
            "skipped_documents": [],
        }

    RagChunk.objects.all().delete()
    RagDocument.objects.all().delete()

    total_chunks = 0
    indexed_documents = 0
    skipped_documents: list[dict[str, str]] = []

    for doc_path in doc_paths:
        try:
            raw_text = extract_text_from_path(doc_path)
        except Exception as exc:
            skipped_documents.append({"title": doc_path.name, "reason": f"extract_error:{exc.__class__.__name__}"})
            continue

        if should_preprocess(raw_text):
            raw_text = preprocess_text(raw_text)

        chunks = chunk_text(raw_text)
        if not chunks:
            skipped_documents.append({"title": doc_path.name, "reason": "empty_or_unreadable_text"})
            continue

        doc = RagDocument.objects.create(source=str(doc_path), title=doc_path.name)
        RagChunk.objects.bulk_create(
            [
                RagChunk(document=doc, chunk_idx=index, chunk_text=chunk)
                for index, chunk in enumerate(chunks)
            ]
        )
        indexed_documents += 1
        total_chunks += len(chunks)

    return {
        "count": total_chunks,
        "message": "인덱싱 완료",
        "source_mode": source_mode,
        "source_dir": str(source_dir),
        "total_documents": len(doc_paths),
        "indexed_documents": indexed_documents,
        "skipped_documents": skipped_documents,
    }


def list_rag_documents() -> list[dict[str, Any]]:
    rows = RagDocument.objects.annotate(chunk_count=Count("chunks")).order_by("-id")
    return [
        {
            "id": row.id,
            "title": row.title,
            "source": row.source,
            "chunk_count": row.chunk_count,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def get_rag_document_preview(doc_id: int, limit: int = 5) -> tuple[RagDocument | None, list[dict[str, Any]]]:
    document = RagDocument.objects.filter(id=doc_id).first()
    if not document:
        return None, []

    chunks = list(document.chunks.order_by("chunk_idx")[: max(1, min(20, int(limit)))])
    payload = [{"chunk_idx": row.chunk_idx, "chunk_text": row.chunk_text} for row in chunks]
    return document, payload


def rag_parse_info() -> dict[str, Any]:
    return {
        "source_dir": str(get_upload_source_dir()),
        "fallback_dir": str(get_fallback_source_dir()),
        "target_docs": ["*.pdf", "*.docx", "*.txt", "*.md"],
        "selection_rule": "업로드 폴더 우선, 없으면 fallback 폴더 사용",
        "extractor": "pdf: pypdf / docx: word/document.xml / text: utf-8",
        "preprocess_rule": "줄바꿈 비율이 높으면 하이픈 줄바꿈 제거 + 공백 정리",
        "chunking": "chunk_size=600, overlap=120",
        "embed_model": "N/A (v1에서는 키워드 기반 검색만 사용)",
    }
