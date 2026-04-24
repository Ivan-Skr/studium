from django.contrib.auth.forms import UserCreationForm

from .models import User


class ExtendedUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        # Поля, которые пользователь должен заполнить при регистрации
        fields = ("username", "email", "is_student", "is_teacher")
