
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from .models import (
    ChildChatMessage,
    ChildProfile,
    ChildTodo,
    ParentChild,
    UserRole,
)
from .services import (
    AppRuntimeConfig,
    build_keyword_cloud,
    call_fastapi_chat,
    call_fastapi_keywords,
    create_sentiment_alert,
    ensure_child_consent_row,
    ensure_upload_source_dir,
    get_rag_document_preview,
    get_runtime_config,
    get_runtime_config_view,
    has_child_consent,
    list_available_models,
    list_child_consents,
    list_open_alerts,
    list_rag_documents,
    rag_parse_info,
    reindex_documents,
    resolve_alert,
    set_child_consent,
    set_runtime_config,
    sync_keyword_observations,
    validate_child_prompt_template,
    validate_prompt_template,
)


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _is_admin(user: User) -> bool:
    return bool(user.is_staff or user.is_superuser)


def _safe_json(request: HttpRequest) -> dict[str, Any]:
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except JSONDecodeError as exc:
        raise ValueError("invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    return payload


def _parse_priority(raw_value: Any, default: int = 3) -> int:
    if raw_value in {None, ""}:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("priority must be integer") from exc
    return max(1, min(5, value))


def _parse_due_date(raw_value: Any) -> date | None:
    if raw_value in {None, ""}:
        return None
    if not isinstance(raw_value, str):
        raise ValueError("due_date must be string")
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError("due_date must be YYYY-MM-DD") from exc


def _username_valid(value: str) -> tuple[bool, str]:
    username = (value or "").strip()
    if not username:
        return False, "아이디를 입력하세요."
    if len(username) < 3:
        return False, "아이디는 3자 이상이어야 합니다."
    return True, username


def _password_valid(value: str) -> tuple[bool, str]:
    password = (value or "").strip()
    if len(password) < 4:
        return False, "비밀번호는 4자 이상이어야 합니다."
    return True, password


def _derive_role(user: User) -> str:
    if _is_admin(user):
        return "admin"
    if ParentChild.objects.filter(parent=user).exists():
        return "parent"
    if _is_child_account(user):
        return "child"
    return "user"


def _ensure_role_profile(user: User, role: str) -> None:
    UserRole.objects.update_or_create(user=user, defaults={"role": role})


def _is_child_account(user: User) -> bool:
    return bool(ParentChild.objects.filter(child=user).exists() or hasattr(user, "child_profile"))


def _admin_users() -> list[dict[str, Any]]:
    users = User.objects.order_by("id")
    parent_ids = set(ParentChild.objects.values_list("parent_id", flat=True))
    child_ids = set(ParentChild.objects.values_list("child_id", flat=True))
    result: list[dict[str, Any]] = []

    for user in users:
        role = "user"
        if _is_admin(user):
            role = "admin"
        elif user.id in parent_ids:
            role = "parent"
        elif user.id in child_ids or ChildProfile.objects.filter(child=user).exists():
            role = "child"

        result.append(
            {
                "id": user.id,
                "username": user.username,
                "role": role,
                "is_admin": _is_admin(user),
                "date_joined": user.date_joined,
            }
        )

    return result


def home(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("/login")

    if _is_admin(request.user):
        return redirect("/admin")

    parent_links = ParentChild.objects.filter(parent=request.user)
    if parent_links.exists():
        return redirect("/parent")
    return redirect("/child/chat")


@login_required
@ensure_csrf_cookie
@require_GET
def admin_portal(request: HttpRequest) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    total_users = User.objects.count()
    total_children = User.objects.filter(parents__isnull=False).distinct().count()
    total_todos = ChildTodo.objects.count()
    done_todos = ChildTodo.objects.filter(status=ChildTodo.STATUS_DONE).count()
    recent_messages = ChildChatMessage.objects.select_related("child").order_by("-created_at")[:20]

    return render(
        request,
        "admin_portal.html",
        {
            "total_users": total_users,
            "total_children": total_children,
            "total_todos": total_todos,
            "done_todos": done_todos,
            "recent_messages": recent_messages,
            "alerts": list_open_alerts(limit=20),
            "users": _admin_users(),
            "ai_config": get_runtime_config_view(),
        },
    )


@login_required
@require_http_methods(["POST"])
def admin_resolve_alert(request: HttpRequest, alert_id: int) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    if resolve_alert(alert_id, request.user):
        messages.success(request, "알림을 확인 처리했습니다.")
    else:
        messages.error(request, "알림을 찾을 수 없습니다.")
    return redirect("/admin")


@login_required
@require_http_methods(["POST"])
def admin_update_openai_config(request: HttpRequest) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    llm_provider = str(request.POST.get("llm_provider", "rule")).strip().lower() or "rule"
    llm_base_url = str(request.POST.get("llm_base_url", "")).strip()
    openai_model = str(request.POST.get("openai_model", "")).strip()
    openai_api_key = str(request.POST.get("openai_api_key", "")).strip()
    if not openai_model:
        messages.error(request, "모델명을 입력하세요.")
        return redirect("/admin")

    updates: dict[str, str] = {
        AppRuntimeConfig.KEY_LLM_PROVIDER: llm_provider,
        AppRuntimeConfig.KEY_LLM_BASE_URL: llm_base_url,
        AppRuntimeConfig.KEY_OPENAI_MODEL: openai_model,
    }
    if openai_api_key:
        updates[AppRuntimeConfig.KEY_OPENAI_API_KEY] = openai_api_key

    set_runtime_config(updates, updated_by=request.user)
    messages.success(request, "LLM 설정을 저장했습니다.")
    return redirect("/admin")


@login_required
@require_GET
def admin_list_openai_models(request: HttpRequest) -> JsonResponse:
    if not _is_admin(request.user):
        return _json_error("forbidden", status=403)

    runtime_config = get_runtime_config()
    current_model = runtime_config.get(AppRuntimeConfig.KEY_OPENAI_MODEL, "gpt-4o-mini")
    llm_provider = str(
        request.GET.get("provider")
        or runtime_config.get(AppRuntimeConfig.KEY_LLM_PROVIDER, "rule")
    ).strip()
    llm_base_url = str(
        request.GET.get("base_url")
        or runtime_config.get(AppRuntimeConfig.KEY_LLM_BASE_URL, "")
    ).strip()
    api_key = runtime_config.get(AppRuntimeConfig.KEY_OPENAI_API_KEY, "")
    models = list_available_models(
        provider=llm_provider,
        base_url=llm_base_url,
        api_key=api_key,
    )

    return JsonResponse(
        {
            "models": models,
            "current_model": current_model,
            "error": "",
        }
    )


@login_required
@require_http_methods(["POST"])
def admin_update_prompt_config(request: HttpRequest) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    system_prompt = str(request.POST.get("system_prompt", "")).strip()
    user_prompt_template = str(request.POST.get("user_prompt_template", "")).strip()
    child_system_prompt = str(request.POST.get("child_system_prompt", "")).strip()
    child_user_prompt_template = str(request.POST.get("child_user_prompt_template", "")).strip()

    if not system_prompt:
        messages.error(request, "시스템 프롬프트는 비워둘 수 없습니다.")
        return redirect("/admin")
    if not child_system_prompt:
        messages.error(request, "자녀 시스템 프롬프트는 비워둘 수 없습니다.")
        return redirect("/admin")

    ok, message = validate_prompt_template(user_prompt_template)
    if not ok:
        messages.error(request, message)
        return redirect("/admin")

    ok, message = validate_child_prompt_template(child_user_prompt_template)
    if not ok:
        messages.error(request, message)
        return redirect("/admin")

    set_runtime_config(
        {
            AppRuntimeConfig.KEY_SYSTEM_PROMPT: system_prompt,
            AppRuntimeConfig.KEY_USER_PROMPT_TEMPLATE: user_prompt_template,
            AppRuntimeConfig.KEY_CHILD_SYSTEM_PROMPT: child_system_prompt,
            AppRuntimeConfig.KEY_CHILD_USER_PROMPT_TEMPLATE: child_user_prompt_template,
        },
        updated_by=request.user,
    )
    messages.success(request, "프롬프트 설정을 저장했습니다.")
    return redirect("/admin")


@login_required
@require_http_methods(["POST"])
def admin_create_parent(request: HttpRequest) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    ok, username_or_message = _username_valid(request.POST.get("username", ""))
    if not ok:
        messages.error(request, username_or_message)
        return redirect("/admin")
    username = username_or_message

    ok, password_or_message = _password_valid(request.POST.get("password", ""))
    if not ok:
        messages.error(request, password_or_message)
        return redirect("/admin")
    password = password_or_message

    if User.objects.filter(username=username).exists():
        messages.error(request, "이미 사용 중인 아이디입니다.")
        return redirect("/admin")

    user = User.objects.create_user(username=username, password=password)
    _ensure_role_profile(user, UserRole.ROLE_PARENT)
    messages.success(request, f"부모 계정 생성 완료: {username}")
    return redirect("/admin")


@login_required
@require_http_methods(["POST"])
def admin_create_child(request: HttpRequest) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    ok, username_or_message = _username_valid(request.POST.get("username", ""))
    if not ok:
        messages.error(request, username_or_message)
        return redirect("/admin")
    username = username_or_message

    ok, password_or_message = _password_valid(request.POST.get("password", ""))
    if not ok:
        messages.error(request, password_or_message)
        return redirect("/admin")
    password = password_or_message

    if User.objects.filter(username=username).exists():
        messages.error(request, "이미 사용 중인 아이디입니다.")
        return redirect("/admin")

    grade = str(request.POST.get("grade", "")).strip()
    interests = str(request.POST.get("interests", "")).strip()
    guidance = str(request.POST.get("guidance", "")).strip()
    parent_id_raw = str(request.POST.get("parent_id", "")).strip()

    child = User.objects.create_user(username=username, password=password)
    _ensure_role_profile(child, UserRole.ROLE_CHILD)

    ChildProfile.objects.update_or_create(
        child=child,
        defaults={
            "grade": grade,
            "interests": interests,
            "guidance": guidance,
        },
    )

    if parent_id_raw:
        try:
            parent_id = int(parent_id_raw)
            parent = User.objects.get(id=parent_id)
            ParentChild.objects.get_or_create(parent=parent, child=child)
        except (ValueError, User.DoesNotExist):
            messages.error(request, "선택한 부모 계정을 찾을 수 없습니다.")
            child.delete()
            return redirect("/admin")

    consent_given = request.POST.get("consent_given") == "on"
    ensure_child_consent_row(child.id, default_given=consent_given)
    if not consent_given:
        set_child_consent(child_id=child.id, consent_given=False, updated_by=request.user)

    messages.success(request, f"자녀 계정 생성 완료: {username}")
    return redirect("/admin")


@login_required
@require_http_methods(["POST"])
def admin_delete_user(request: HttpRequest, user_id: int) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    target = User.objects.filter(id=user_id).first()
    if not target:
        messages.error(request, "삭제할 계정을 찾을 수 없습니다.")
        return redirect("/admin")
    if target == request.user:
        messages.error(request, "현재 로그인한 관리자 계정은 삭제할 수 없습니다.")
        return redirect("/admin")
    if _is_admin(target):
        messages.error(request, "관리자 계정은 삭제할 수 없습니다.")
        return redirect("/admin")

    username = target.username
    target.delete()
    messages.success(request, f"계정 삭제 완료: {username}")
    return redirect("/admin")


@login_required
@require_GET
def admin_user_detail(request: HttpRequest, user_id: int) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    target = get_object_or_404(User, id=user_id)
    role = _derive_role(target)

    child_profile = ChildProfile.objects.filter(child=target).first()
    child_todos = ChildTodo.objects.filter(child=target).order_by("status", "priority", "created_at")
    child_messages = ChildChatMessage.objects.filter(child=target).order_by("created_at")
    child_cloud = build_keyword_cloud(target.id, days=30)
    parent_links = ParentChild.objects.filter(child=target).select_related("parent")
    managed_children = ParentChild.objects.filter(parent=target).select_related("child")

    return render(
        request,
        "admin_user_detail.html",
        {
            "target": target,
            "target_role": role,
            "child_profile": child_profile,
            "child_todos": child_todos,
            "child_messages": child_messages,
            "child_cloud": child_cloud,
            "parent_links": parent_links,
            "managed_children": managed_children,
        },
    )


@login_required
@require_GET
def admin_consents_get(request: HttpRequest) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    return render(
        request,
        "admin_consents.html",
        {
            "consents": list_child_consents(),
        },
    )


@login_required
@require_http_methods(["POST"])
def admin_consent_grant(request: HttpRequest, child_id: int) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    child = User.objects.filter(id=child_id).first()
    if not child:
        messages.error(request, "자녀 계정을 찾을 수 없습니다.")
        return redirect("/admin/consents")

    set_child_consent(child_id=child.id, consent_given=True, updated_by=request.user)
    messages.success(request, f"AI 동의 처리 완료: {child.username}")
    return redirect("/admin/consents")


@login_required
@require_http_methods(["POST"])
def admin_consent_revoke(request: HttpRequest, child_id: int) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    child = User.objects.filter(id=child_id).first()
    if not child:
        messages.error(request, "자녀 계정을 찾을 수 없습니다.")
        return redirect("/admin/consents")

    set_child_consent(child_id=child.id, consent_given=False, updated_by=request.user)
    messages.success(request, f"AI 동의 철회 완료: {child.username}")
    return redirect("/admin/consents")


@login_required
@require_GET
def rag_reindex(request: HttpRequest) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    result = reindex_documents()
    total_documents = int(result.get("total_documents", 0))
    indexed_documents = int(result.get("indexed_documents", 0))
    total_chunks = int(result.get("count", 0))
    skipped_documents = result.get("skipped_documents", [])

    if total_documents == 0:
        messages.warning(request, str(result.get("message", "색인할 문서가 없습니다.")))
    else:
        messages.success(
            request,
            f"문서 재색인 완료: 대상 {total_documents}건, 색인 {indexed_documents}건, 총 청크 {total_chunks}개",
        )

    if skipped_documents:
        preview = ", ".join(item.get("title", "-") for item in skipped_documents[:3])
        suffix = " 등" if len(skipped_documents) > 3 else ""
        messages.warning(request, f"미색인 문서: {preview}{suffix}")

    return redirect("/admin/rag/index")


@login_required
@require_GET
def admin_rag_index(request: HttpRequest) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    doc_id_raw = request.GET.get("doc_id")
    doc_id = None
    if doc_id_raw:
        try:
            doc_id = int(doc_id_raw)
        except ValueError:
            doc_id = None

    selected_doc = None
    preview_chunks: list[dict[str, Any]] = []
    if doc_id is not None:
        selected_doc, preview_chunks = get_rag_document_preview(doc_id)

    return render(
        request,
        "admin_rag_index.html",
        {
            "docs": list_rag_documents(),
            "selected_doc": selected_doc,
            "preview_chunks": preview_chunks,
            "parse_info": rag_parse_info(),
            "users": _admin_users(),
        },
    )


@login_required
@require_http_methods(["POST"])
def admin_rag_upload(request: HttpRequest) -> HttpResponse:
    if not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    upload = request.FILES.get("document")
    if not upload or not upload.name:
        messages.error(request, "업로드할 파일명을 확인하세요.")
        return redirect("/admin/rag/index")

    original_name = Path(upload.name).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        messages.error(request, "PDF/DOCX/TXT/MD 파일만 업로드할 수 있습니다.")
        return redirect("/admin/rag/index")

    source_dir = ensure_upload_source_dir()
    target_path = source_dir / original_name
    if target_path.exists():
        stem = target_path.stem
        ext = target_path.suffix
        index = 1
        while True:
            candidate = source_dir / f"{stem}_{index}{ext}"
            if not candidate.exists():
                target_path = candidate
                break
            index += 1

    with target_path.open("wb") as fp:
        for chunk in upload.chunks():
            fp.write(chunk)

    messages.success(request, f"업로드 완료: {target_path.name}")
    return redirect("/admin/rag/index")


@login_required
@require_GET
def export_csv(request: HttpRequest) -> HttpResponse:
    scope = str(request.GET.get("scope", "messages"))
    user_id_raw = request.GET.get("user_id")
    user_id = int(user_id_raw) if user_id_raw and user_id_raw.isdigit() else None

    if not _is_admin(request.user):
        scope = "messages"
        user_id = request.user.id

    output = io.StringIO()
    writer = csv.writer(output)

    queryset = ChildChatMessage.objects.select_related("child").order_by("id")
    if user_id:
        queryset = queryset.filter(child_id=user_id)

    if scope == "metrics":
        writer.writerow(["child_id", "username", "role", "content", "created_at", "sentiment", "topics"])
        for row in queryset:
            topics = list(row.keywordobservation_set.values("term", "weight", "polarity"))
            writer.writerow(
                [
                    row.child_id,
                    row.child.username,
                    row.role,
                    row.content,
                    row.created_at.isoformat(),
                    row.sentiment,
                    json.dumps(topics, ensure_ascii=False),
                ]
            )
    else:
        writer.writerow(["child_id", "username", "role", "content", "created_at"])
        for row in queryset:
            writer.writerow([row.child_id, row.child.username, row.role, row.content, row.created_at.isoformat()])

    output.seek(0)
    filename = "export_metrics.csv" if scope == "metrics" else "export_messages.csv"
    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@login_required
@ensure_csrf_cookie
@require_GET
def parent_dashboard(request: HttpRequest) -> HttpResponse:
    if _is_admin(request.user) or _is_child_account(request.user):
        return HttpResponse("forbidden", status=403)

    links = ParentChild.objects.filter(parent=request.user).select_related("child")
    children = []
    for link in links:
        child = link.child
        todo_total = child.todos.count()
        todo_done = child.todos.filter(status=ChildTodo.STATUS_DONE).count()
        last_chat = child.chat_messages.order_by("-created_at").first()
        completion = round((todo_done / todo_total) * 100, 1) if todo_total else 0.0
        children.append(
            {
                "id": child.id,
                "username": child.username,
                "todo_total": todo_total,
                "todo_done": todo_done,
                "completion_pct": completion,
                "last_chat_at": last_chat.created_at if last_chat else None,
            }
        )

    return render(request, "parent_dashboard.html", {"children": children})


@login_required
@require_http_methods(["POST"])
def parent_create_child(request: HttpRequest) -> HttpResponse:
    if _is_admin(request.user) or _is_child_account(request.user):
        return HttpResponse("forbidden", status=403)

    ok, username_or_message = _username_valid(request.POST.get("username", ""))
    if not ok:
        messages.error(request, username_or_message)
        return redirect("/parent")
    username = username_or_message

    ok, password_or_message = _password_valid(request.POST.get("password", ""))
    if not ok:
        messages.error(request, password_or_message)
        return redirect("/parent")
    password = password_or_message

    if User.objects.filter(username=username).exists():
        messages.error(request, "이미 사용 중인 아이디입니다.")
        return redirect("/parent")

    grade = str(request.POST.get("grade", "")).strip()
    interests = str(request.POST.get("interests", "")).strip()
    guidance = str(request.POST.get("guidance", "")).strip()

    child = User.objects.create_user(username=username, password=password)
    _ensure_role_profile(child, UserRole.ROLE_CHILD)
    ChildProfile.objects.update_or_create(
        child=child,
        defaults={"grade": grade, "interests": interests, "guidance": guidance},
    )
    ParentChild.objects.get_or_create(parent=request.user, child=child)
    ensure_child_consent_row(child.id, default_given=True)

    messages.success(request, f"자녀 계정 생성 완료: {username}")
    return redirect("/parent")


@login_required
@ensure_csrf_cookie
@require_GET
def parent_child_detail(request: HttpRequest, child_id: int) -> HttpResponse:
    child = get_object_or_404(User, id=child_id)
    link = ParentChild.objects.filter(parent=request.user, child=child).first()
    if not link and not _is_admin(request.user):
        return HttpResponse("forbidden", status=403)

    selected_chat_date = str(request.GET.get("chat_date", "")).strip()
    parsed_chat_date: date | None = None
    if selected_chat_date:
        try:
            parsed_chat_date = date.fromisoformat(selected_chat_date)
        except ValueError:
            selected_chat_date = ""

    todos = ChildTodo.objects.filter(child=child).order_by("status", "priority", "created_at")
    cloud = build_keyword_cloud(child.id, days=7)
    chat_messages_qs = ChildChatMessage.objects.filter(child=child)
    if parsed_chat_date:
        start_dt = datetime.combine(parsed_chat_date, time.min, tzinfo=dt_timezone.utc)
        end_dt = start_dt + timedelta(days=1)
        chat_messages_qs = chat_messages_qs.filter(created_at__gte=start_dt, created_at__lt=end_dt)

    chat_messages_rows = chat_messages_qs.order_by("-created_at")[:50]
    available_chat_dates = [
        entry.isoformat()
        for entry in ChildChatMessage.objects.filter(child=child).dates("created_at", "day", order="DESC")[:30]
    ]
    todo_done_dates = sorted(
        {
            done_at.date().isoformat()
            for done_at in todos.filter(done_at__isnull=False).values_list("done_at", flat=True)
            if done_at
        }
    )
    profile = ChildProfile.objects.filter(child=child).first()

    return render(
        request,
        "parent_child_detail.html",
        {
            "child": child,
            "profile": profile,
            "todos": todos,
            "cloud": cloud,
            "chat_messages": list(reversed(chat_messages_rows)),
            "selected_chat_date": selected_chat_date,
            "available_chat_dates": available_chat_dates,
            "todo_done_dates": todo_done_dates,
        },
    )


@login_required
@ensure_csrf_cookie
@require_GET
def child_chat_page(request: HttpRequest) -> HttpResponse:
    session_id = request.session.get("chat_session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session["chat_session_id"] = session_id

    profile = ChildProfile.objects.filter(child=request.user).first()
    chat_messages_rows = ChildChatMessage.objects.filter(child=request.user).order_by("created_at")[:80]
    todos = ChildTodo.objects.filter(child=request.user).order_by("status", "priority", "created_at")

    return render(
        request,
        "child_chat.html",
        {
            "session_id": session_id,
            "profile": profile,
            "chat_messages": chat_messages_rows,
            "todos": todos,
            "pending_todo_count": todos.exclude(status=ChildTodo.STATUS_DONE).count(),
            "consent_given": has_child_consent(request.user.id),
        },
    )


@login_required
@require_http_methods(["POST"])
def api_create_todo(request: HttpRequest, child_id: int) -> JsonResponse:
    child = get_object_or_404(User, id=child_id)
    if not ParentChild.objects.filter(parent=request.user, child=child).exists() and not _is_admin(request.user):
        return _json_error("forbidden", status=403)

    try:
        payload = _safe_json(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    title = str(payload.get("title", "")).strip()
    if not title:
        return _json_error("title is required", status=400)

    try:
        priority = _parse_priority(payload.get("priority"), default=3)
        due_date = _parse_due_date(payload.get("due_date"))
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    todo = ChildTodo.objects.create(
        child=child,
        title=title,
        priority=priority,
        due_date=due_date,
    )

    return JsonResponse(
        {
            "id": todo.id,
            "child_id": child.id,
            "title": todo.title,
            "status": todo.status,
            "priority": todo.priority,
            "due_date": todo.due_date.isoformat() if todo.due_date else None,
        },
        status=201,
    )


@login_required
@require_http_methods(["PATCH"])
def api_patch_todo(request: HttpRequest, todo_id: int) -> JsonResponse:
    todo = get_object_or_404(ChildTodo, id=todo_id)
    if not ParentChild.objects.filter(parent=request.user, child=todo.child).exists() and not _is_admin(request.user):
        return _json_error("forbidden", status=403)

    try:
        payload = _safe_json(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    if "status" in payload:
        try:
            todo.transition_to(str(payload.get("status")))
        except ValueError:
            return _json_error("invalid status transition", status=400)

    update_fields: list[str] = []
    if "title" in payload:
        stripped_title = str(payload.get("title", "")).strip()
        if stripped_title:
            todo.title = stripped_title
            update_fields.append("title")
    if "priority" in payload:
        try:
            todo.priority = _parse_priority(payload.get("priority"), default=todo.priority)
        except ValueError as exc:
            return _json_error(str(exc), status=400)
        update_fields.append("priority")

    if update_fields:
        update_fields.append("updated_at")
        todo.save(update_fields=update_fields)

    return JsonResponse(
        {
            "id": todo.id,
            "status": todo.status,
            "title": todo.title,
            "priority": todo.priority,
            "done_at": todo.done_at.isoformat() if todo.done_at else None,
        }
    )


@login_required
@require_http_methods(["POST"])
def api_chat_send(request: HttpRequest) -> JsonResponse:
    try:
        payload = _safe_json(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    child_id = int(payload.get("child_id") or request.user.id)
    user_text = str(payload.get("user_text", "")).strip()
    session_id = str(payload.get("session_id") or request.session.get("chat_session_id") or uuid.uuid4())

    if not user_text:
        return _json_error("user_text is required", status=400)

    child = get_object_or_404(User, id=child_id)
    if (
        child != request.user
        and not ParentChild.objects.filter(parent=request.user, child=child).exists()
        and not _is_admin(request.user)
    ):
        return _json_error("forbidden", status=403)

    if not has_child_consent(child.id):
        return _json_error("AI 사용 동의가 필요합니다.", status=403)

    profile = ChildProfile.objects.filter(child=child).first()
    history_rows = ChildChatMessage.objects.filter(child=child).order_by("-created_at")[:20]
    history = [{"role": row.role, "content": row.content} for row in reversed(history_rows)]
    profile_payload = {
        "grade": profile.grade if profile else "",
        "interests": profile.interests_list() if profile else [],
        "guidance": profile.guidance if profile else "",
    }
    runtime = get_runtime_config()
    llm_config = {
        "provider": runtime.get(AppRuntimeConfig.KEY_LLM_PROVIDER, "rule"),
        "model": runtime.get(AppRuntimeConfig.KEY_OPENAI_MODEL, "gpt-4o-mini"),
        "api_key": runtime.get(AppRuntimeConfig.KEY_OPENAI_API_KEY, ""),
        "base_url": runtime.get(AppRuntimeConfig.KEY_LLM_BASE_URL, ""),
    }

    try:
        ai_response = call_fastapi_chat(
            {
                "session_id": session_id,
                "child_id": child.id,
                "user_text": user_text,
                "history": history,
                "child_profile": profile_payload,
                "llm_config": llm_config,
            }
        )
    except Exception:
        return _json_error("ai backend unavailable", status=502)

    user_msg = ChildChatMessage.objects.create(
        child=child,
        session_id=session_id,
        role=ChildChatMessage.ROLE_CHILD,
        content=user_text,
        sentiment=ai_response.get("sentiment", "neutral"),
    )

    ai_msg = ChildChatMessage.objects.create(
        child=child,
        session_id=session_id,
        role=ChildChatMessage.ROLE_AI,
        content=ai_response.get("reply_text", ""),
        sentiment=ai_response.get("sentiment", "neutral"),
    )

    topics = ai_response.get("topics", [])
    sync_keyword_observations(
        child_id=child.id,
        message=user_msg,
        topics=topics,
        sentiment=ai_response.get("sentiment", "neutral"),
    )
    create_sentiment_alert(child_id=child.id, message=user_msg, sentiment=ai_response.get("sentiment", "neutral"))

    return JsonResponse(
        {
            "session_id": session_id,
            "message_id": ai_msg.id,
            "reply_text": ai_msg.content,
            "sentiment": ai_msg.sentiment,
            "topics": topics,
            "suggested_todos": ai_response.get("suggested_todos", []),
        }
    )


@login_required
@require_GET
def api_keyword_cloud(request: HttpRequest, child_id: int) -> JsonResponse:
    try:
        days = int(request.GET.get("days", 7) or 7)
    except ValueError:
        return _json_error("days must be integer", status=400)

    child = get_object_or_404(User, id=child_id)
    if (
        child != request.user
        and not ParentChild.objects.filter(parent=request.user, child=child).exists()
        and not _is_admin(request.user)
    ):
        return _json_error("forbidden", status=403)

    texts = list(
        ChildChatMessage.objects.filter(child=child, role=ChildChatMessage.ROLE_CHILD)
        .order_by("-created_at")
        .values_list("content", flat=True)[:100]
    )
    try:
        remote = call_fastapi_keywords(child.id, texts=texts, window_days=days)
    except Exception:
        remote = {
            "top_keywords": [],
            "summary": {"positive_ratio": 0.0, "neutral_ratio": 1.0, "negative_ratio": 0.0},
        }

    local_cloud = build_keyword_cloud(child.id, days=days)

    return JsonResponse(
        {
            "child_id": child.id,
            "window_days": days,
            "summary": remote.get("summary", {}),
            "top_keywords": remote.get("top_keywords", []),
            "keyword_cloud": local_cloud,
        }
    )
