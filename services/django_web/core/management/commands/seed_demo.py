
from __future__ import annotations

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from services.django_web.core.models import ChildProfile, ChildTodo, ParentChild, UserRole


class Command(BaseCommand):
    help = "Create demo users and sample data for YouOnlyTalkOnce"

    def handle(self, *args, **options):
        admin, _ = User.objects.get_or_create(username="admin")
        admin.is_staff = True
        admin.is_superuser = True
        admin.set_password("admin1234")
        admin.save()
        UserRole.objects.get_or_create(user=admin, defaults={"role": UserRole.ROLE_ADMIN})

        parent, _ = User.objects.get_or_create(username="parent_demo")
        parent.set_password("parent1234")
        parent.save()
        UserRole.objects.get_or_create(user=parent, defaults={"role": UserRole.ROLE_PARENT})

        child, _ = User.objects.get_or_create(username="child_demo")
        child.set_password("child1234")
        child.save()
        UserRole.objects.get_or_create(user=child, defaults={"role": UserRole.ROLE_CHILD})

        ParentChild.objects.get_or_create(parent=parent, child=child)
        ChildProfile.objects.get_or_create(
            child=child,
            defaults={
                "grade": "초5",
                "interests": "축구,독서,과학",
                "guidance": "숙제 우선 후 놀이",
            },
        )

        ChildTodo.objects.get_or_create(child=child, title="수학 숙제 2쪽", defaults={"priority": 1})
        ChildTodo.objects.get_or_create(child=child, title="영어 단어 20개", defaults={"priority": 2})

        self.stdout.write(self.style.SUCCESS("Demo data created: admin/parent_demo/child_demo"))
