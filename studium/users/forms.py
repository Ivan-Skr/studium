from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)

from .models import User


class EmailAuthenticationForm(AuthenticationForm):
    """Логин по email или username + пароль."""

    username = forms.CharField(
        label="Email или имя пользователя",
        widget=forms.TextInput(attrs={"placeholder": "your@email.com или username"}),
    )


class RegisterForm(UserCreationForm):
    """Регистрация: username, имя, фамилия, email, пароль и роль."""

    ROLE_CHOICES = (
        ("student", "Студент"),
        ("teacher", "Преподаватель"),
    )

    first_name = forms.CharField(label="Имя", max_length=150, required=True)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=True)
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES, initial="student")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
            "role",
        )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        role = self.cleaned_data.get("role", "student")
        user.is_student = role == "student"
        user.is_teacher = role == "teacher"
        if commit:
            user.save()
        return user


class EditProfileForm(forms.ModelForm):
    """Редактирование username, имени, фамилии, email и аватара."""

    first_name = forms.CharField(label="Имя", max_length=150, required=True)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=True)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "avatar")

    def clean_email(self):
        email = self.cleaned_data.get("email")
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email


class CustomPasswordChangeForm(PasswordChangeForm):
    """Просто переименовываем поля в русскоязычные лейблы."""

    old_password = forms.CharField(
        label="Текущий пароль",
        widget=forms.PasswordInput(attrs={"placeholder": "••••••••"}),
    )
    new_password1 = forms.CharField(
        label="Новый пароль",
        widget=forms.PasswordInput(attrs={"placeholder": "••••••••"}),
    )
    new_password2 = forms.CharField(
        label="Подтверждение нового пароля",
        widget=forms.PasswordInput(attrs={"placeholder": "••••••••"}),
    )
