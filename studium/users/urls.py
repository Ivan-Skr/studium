from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    # Встроенный LoginView ищет шаблон по умолчанию в registration/login.html
    path("login/", LoginView.as_view(template_name="users/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
]
