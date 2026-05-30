from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.crypto import get_random_string


class User(AbstractUser):
    # Роли
    is_student = models.BooleanField(default=True)
    is_teacher = models.BooleanField(default=False)

    # Доп поля
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    learning_seconds = models.PositiveIntegerField(default=0)
    calendar_token = models.CharField(max_length=64, unique=True, blank=True)

    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        if not self.calendar_token:
            self.calendar_token = get_random_string(64)
        super().save(*args, **kwargs)

    @property
    def learning_hours_display(self):
        return round(self.learning_seconds / 3600, 1)

    @property
    def role_display(self):
        return "Преподаватель" if self.is_teacher else "Студент"
