from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("login/", views.UsersLoginView.as_view(), name="login"),
    path("logout/", views.UsersLogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("certificates/", views.certificates, name="certificates"),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
    path("profile/change-password/", views.change_password, name="change_password"),
]
