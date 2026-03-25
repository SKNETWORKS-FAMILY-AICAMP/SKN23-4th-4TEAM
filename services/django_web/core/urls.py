
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home),
    path("admin", views.admin_portal),
    path("admin/alerts/<int:alert_id>/resolve", views.admin_resolve_alert),
    path("admin/config/openai", views.admin_update_openai_config),
    path("admin/config/models", views.admin_list_openai_models),
    path("admin/config/prompts", views.admin_update_prompt_config),
    path("admin/users/parent", views.admin_create_parent),
    path("admin/users/child", views.admin_create_child),
    path("admin/users/<int:user_id>/delete", views.admin_delete_user),
    path("admin/user/<int:user_id>", views.admin_user_detail),
    path("admin/consents", views.admin_consents_get),
    path("admin/consents/<int:child_id>/grant", views.admin_consent_grant),
    path("admin/consents/<int:child_id>/revoke", views.admin_consent_revoke),
    path("rag/reindex", views.rag_reindex),
    path("admin/rag/index", views.admin_rag_index),
    path("admin/rag/upload", views.admin_rag_upload),
    path("export/csv", views.export_csv),
    path("parent", views.parent_dashboard),
    path("parent/children/create", views.parent_create_child),
    path("parent/child/<int:child_id>", views.parent_child_detail),
    path("child/chat", views.child_chat_page),
    path("api/chat/send", views.api_chat_send),
    path("api/children/<int:child_id>/todos", views.api_create_todo),
    path("api/todos/<int:todo_id>", views.api_patch_todo),
    path("api/children/<int:child_id>/keyword-cloud", views.api_keyword_cloud),
]
