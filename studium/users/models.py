from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # Роли
    is_student = models.BooleanField(default=True)
    is_teacher = models.BooleanField(default=False)

    # Доп поля
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username

    @property
    def role_display(self):
        return "Преподаватель" if self.is_teacher else "Студент"
