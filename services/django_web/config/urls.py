
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("login", LoginView.as_view(template_name="login.html")),
    path("logout", LogoutView.as_view()),
    path("", include("services.django_web.core.urls")),
]
