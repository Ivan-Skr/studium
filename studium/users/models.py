from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # Добавляем роли для LMS
    is_student = models.BooleanField(default=True)
    is_teacher = models.BooleanField(default=False)

    # Дополнительные поля
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    def __str__(self):
        return self.username
