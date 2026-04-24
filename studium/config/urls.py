from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Префикс 'users/', все адреса из приложения будут начинаться с него
    # (например mysite.com/users/login/)
    path("users/", include("users.urls")),
    path("", TemplateView.as_view(template_name="base.html"), name="home"),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
