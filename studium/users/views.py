from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ExtendedUserCreationForm  # Импортируем новую форму


def register(request):
    if request.method == "POST":
        form = ExtendedUserCreationForm(request.POST)  # Используем её здесь
        if form.is_valid():
            form.save()
            # После успешной регистрации перенаправляем на страницу входа
            return redirect("users:login")
    else:
        form = ExtendedUserCreationForm()

    return render(request, "users/register.html", {"form": form})


@login_required
def profile(request):
    # Теперь в шаблоне профиля будет доступен объект request.user со всеми новыми полями
    return render(request, "users/profile.html")
