from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import (
    CustomPasswordChangeForm,
    EditProfileForm,
    EmailAuthenticationForm,
    RegisterForm,
)


class UsersLoginView(LoginView):
    template_name = "users/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class UsersLogoutView(LogoutView):
    next_page = reverse_lazy("users:login")


def register(request):
    if request.user.is_authenticated:
        return redirect("users:profile")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Автологин сразу после успешной регистрации
            login(
                request,
                user,
                backend="users.backends.EmailOrUsernameModelBackend",
            )
            messages.success(request, "Регистрация прошла успешно!")
            return redirect("users:profile")
    else:
        form = RegisterForm()

    return render(request, "users/register.html", {"form": form})


@login_required
def profile(request):
    context = {"user": request.user}
    if request.user.is_teacher:
        from lessons.models import Course

        context["authored_courses"] = Course.objects.filter(
            author=request.user
        ).order_by("-created_at")[:6]
    else:
        from lessons.models import CourseCompletion, CourseEnrollment

        context["enrolled_courses"] = (
            CourseEnrollment.objects.filter(
                student=request.user,
                status=CourseEnrollment.Status.APPROVED,
            )
            .select_related("course", "course__author")
            .order_by("-updated_at")[:6]
        )
        context["enrolled_courses_count"] = CourseEnrollment.objects.filter(
            student=request.user,
            status=CourseEnrollment.Status.APPROVED,
        ).count()
        context["completed_course_ids"] = set(
            CourseCompletion.objects.filter(student=request.user).values_list(
                "course_id", flat=True
            )
        )
        context["completed_courses_count"] = len(context["completed_course_ids"])
        context["certificates_count"] = request.user.certificates.count()
    return render(request, "users/profile.html", context)


@login_required
def certificates(request):
    user_certificates = request.user.certificates.select_related("course").order_by(
        "-issued_at"
    )
    return render(
        request,
        "users/certificates.html",
        {"certificates": user_certificates},
    )


@login_required
def edit_profile(request):
    if request.method == "POST":
        form = EditProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль успешно обновлён!")
            return redirect("users:profile")
    else:
        form = EditProfileForm(instance=request.user)

    return render(request, "users/edit_profile.html", {"form": form})


@login_required
def change_password(request):
    if request.method == "POST":
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Чтобы пользователя не разлогинило после смены пароля
            update_session_auth_hash(request, user)
            messages.success(request, "Пароль успешно изменён!")
            return redirect("users:profile")
    else:
        form = CustomPasswordChangeForm(request.user)

    return render(request, "users/change_password.html", {"form": form})
