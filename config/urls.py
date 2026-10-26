from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from documents.views import RoleBasedLoginView
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", RoleBasedLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("documents/", include("documents.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
