
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class UserRole(models.Model):
    ROLE_ADMIN = "admin"
    ROLE_PARENT = "parent"
    ROLE_CHILD = "child"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_PARENT, "Parent"),
        (ROLE_CHILD, "Child"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="role_profile")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_CHILD)

    def __str__(self) -> str:
        return f"{self.user.username}:{self.role}"


class ChildProfile(models.Model):
    child = models.OneToOneField(User, on_delete=models.CASCADE, related_name="child_profile")
    grade = models.CharField(max_length=64, blank=True, default="")
    interests = models.TextField(blank=True, default="")
    guidance = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def interests_list(self) -> list[str]:
        return [item.strip() for item in self.interests.split(",") if item.strip()]


class ParentChild(models.Model):
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="managed_children")
    child = models.ForeignKey(User, on_delete=models.CASCADE, related_name="parents")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("parent", "child")


class ChildTodo(models.Model):
    STATUS_TODO = "todo"
    STATUS_DOING = "doing"
    STATUS_DONE = "done"
    STATUS_CHOICES = [
        (STATUS_TODO, "Todo"),
        (STATUS_DOING, "Doing"),
        (STATUS_DONE, "Done"),
    ]

    child = models.ForeignKey(User, on_delete=models.CASCADE, related_name="todos")
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_TODO)
    priority = models.PositiveSmallIntegerField(default=3)
    due_date = models.DateField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    VALID_TRANSITIONS = {
        STATUS_TODO: {STATUS_DOING, STATUS_DONE},
        STATUS_DOING: {STATUS_DONE, STATUS_TODO},
        STATUS_DONE: {STATUS_TODO},
    }

    def transition_to(self, next_status: str) -> None:
        next_status = str(next_status)
        allowed = self.VALID_TRANSITIONS.get(self.status, set())
        if next_status not in allowed:
            raise ValueError(f"invalid transition: {self.status} -> {next_status}")

        self.status = next_status
        if next_status == self.STATUS_DONE:
            self.done_at = timezone.now()
        else:
            self.done_at = None
        self.save(update_fields=["status", "done_at", "updated_at"])


class ChildChatMessage(models.Model):
    ROLE_CHILD = "child"
    ROLE_AI = "ai"
    ROLE_CHOICES = [
        (ROLE_CHILD, "Child"),
        (ROLE_AI, "AI"),
    ]

    child = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_messages")
    session_id = models.CharField(max_length=128, db_index=True)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    sentiment = models.CharField(max_length=16, default="neutral")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        content = (self.content or "").strip()
        preview = content[:30] + ("..." if len(content) > 30 else "")
        return f"{self.role}:{preview or '-'}"


class KeywordObservation(models.Model):
    POLARITY_CHOICES = [
        ("positive", "Positive"),
        ("neutral", "Neutral"),
        ("negative", "Negative"),
    ]

    child = models.ForeignKey(User, on_delete=models.CASCADE, related_name="keyword_observations")
    message = models.ForeignKey(ChildChatMessage, null=True, blank=True, on_delete=models.SET_NULL)
    term = models.CharField(max_length=128)
    weight = models.FloatField(default=0.0)
    polarity = models.CharField(max_length=16, choices=POLARITY_CHOICES, default="neutral")
    observed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["child", "observed_at"]),
            models.Index(fields=["child", "term"]),
        ]


class KeywordDailyStat(models.Model):
    child = models.ForeignKey(User, on_delete=models.CASCADE, related_name="keyword_daily_stats")
    stat_date = models.DateField()
    positive_count = models.IntegerField(default=0)
    neutral_count = models.IntegerField(default=0)
    negative_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("child", "stat_date")

    def clean(self) -> None:
        if min(self.positive_count, self.neutral_count, self.negative_count) < 0:
            raise ValidationError("sentiment counts cannot be negative")


class AppRuntimeConfig(models.Model):
    KEY_LLM_PROVIDER = "llm_provider"
    KEY_LLM_BASE_URL = "llm_base_url"
    KEY_OPENAI_MODEL = "openai_model"
    KEY_OPENAI_API_KEY = "openai_api_key"
    KEY_SYSTEM_PROMPT = "system_prompt"
    KEY_USER_PROMPT_TEMPLATE = "user_prompt_template"
    KEY_CHILD_SYSTEM_PROMPT = "child_system_prompt"
    KEY_CHILD_USER_PROMPT_TEMPLATE = "child_user_prompt_template"
    KEY_CHOICES = [
        (KEY_LLM_PROVIDER, "LLM Provider"),
        (KEY_LLM_BASE_URL, "LLM Base URL"),
        (KEY_OPENAI_MODEL, "OpenAI Model"),
        (KEY_OPENAI_API_KEY, "OpenAI API Key"),
        (KEY_SYSTEM_PROMPT, "System Prompt"),
        (KEY_USER_PROMPT_TEMPLATE, "User Prompt Template"),
        (KEY_CHILD_SYSTEM_PROMPT, "Child System Prompt"),
        (KEY_CHILD_USER_PROMPT_TEMPLATE, "Child User Prompt Template"),
    ]

    key = models.CharField(max_length=64, unique=True, choices=KEY_CHOICES)
    value = models.TextField(default="", blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="runtime_config_updates",
    )

    class Meta:
        ordering = ["key"]


class ChildConsent(models.Model):
    child = models.OneToOneField(User, on_delete=models.CASCADE, related_name="ai_consent")
    consent_given = models.BooleanField(default=False)
    consent_version = models.CharField(max_length=16, default="v1")
    consent_text = models.TextField(default="AI 자녀 관리 도우미 사용에 동의합니다.")
    agreed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="child_consent_updates",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)


class ChildMessageAlert(models.Model):
    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    child = models.ForeignKey(User, on_delete=models.CASCADE, related_name="message_alerts")
    message = models.OneToOneField(ChildChatMessage, on_delete=models.CASCADE, related_name="alert")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    reason = models.CharField(max_length=64, default="negative_sentiment")
    score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_message_alerts",
    )

    class Meta:
        ordering = ["-id"]


class RagDocument(models.Model):
    source = models.CharField(max_length=512)
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-id"]


class RagChunk(models.Model):
    document = models.ForeignKey(RagDocument, on_delete=models.CASCADE, related_name="chunks")
    chunk_text = models.TextField()
    chunk_idx = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["chunk_idx", "id"]
        unique_together = ("document", "chunk_idx")
