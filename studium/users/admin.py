from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_student",
        "is_teacher",
        "is_staff",
    )
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("LMS", {"fields": ("is_student", "is_teacher", "bio", "avatar")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("LMS", {"fields": ("email", "is_student", "is_teacher")}),
    )
