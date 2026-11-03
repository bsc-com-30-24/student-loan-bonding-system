from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenRefreshView

from authentication.views import (
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegistrationView,
    RoleTokenObtainPairView,
)
from documents.views import RoleBasedLoginView

urlpatterns = [
    # Django administration and login
    path("admin/", admin.site.urls),
    path("login/", RoleBasedLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Document management
    path("documents/", include("documents.urls")),

    # Bond status tracking API
    path("api/bonds/", include("bonds.urls")),

    # Agreement management API
    path("api/agreements/", include("agreements.urls")),

    # Verification API
    path("api/verification/", include("verification.urls")),

    # Reporting API
    path("api/reports/", include("reporting.urls")),

    # Authentication (JWT, registration, password reset)
    path("api/register/", RegistrationView.as_view(), name="register"),
    path("api/token/", RoleTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path(
        "api/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),

    # API schema and documentation
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(permission_classes=[AllowAny], url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(permission_classes=[AllowAny], url_name="schema"),
        name="redoc",
    ),

    # Django REST Framework browser authentication
    path("api-auth/", include("rest_framework.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)