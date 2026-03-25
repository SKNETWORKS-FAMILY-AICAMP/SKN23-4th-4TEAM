
from __future__ import annotations

from .models import ChildProfile, ParentChild


def role_flags(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "nav_is_admin": False,
            "nav_is_parent": False,
            "nav_is_child": False,
        }

    is_admin = bool(user.is_staff or user.is_superuser)
    is_parent = ParentChild.objects.filter(parent=user).exists()
    is_child = ParentChild.objects.filter(child=user).exists() or ChildProfile.objects.filter(child=user).exists()

    return {
        "nav_is_admin": is_admin,
        "nav_is_parent": is_parent,
        "nav_is_child": is_child and not is_admin,
    }
