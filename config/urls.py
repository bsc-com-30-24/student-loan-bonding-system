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
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from authentication.views import (
    LoanApplicationViewSet,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegistrationView,
    RoleTokenObtainPairView,
    StudentDetailMeView,
    StudentDetailViewSet,
)
from documents.views import RoleBasedLoginView

router = DefaultRouter()
router.register("loans", LoanApplicationViewSet, basename="loan-application")
router.register("students", StudentDetailViewSet, basename="student-detail")

urlpatterns = [
    # Django administration and login
    path("admin/", admin.site.urls),
    path("login/", RoleBasedLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Document management (paths start with api/ or documents/ themselves)
    path("", include("documents.urls")),

    # Bond status tracking API
    path("api/bonds/", include("bonds.urls")),

    # Agreement management API
    path("api/agreements/", include("agreements.urls")),

    # Tuition applications, student details, reports and bond checks
    path("api/students/me/", StudentDetailMeView.as_view(), name="student-detail-me"),
    path("api/", include(router.urls)),
    path("api/reports/", include("reporting.urls")),
    path("api/verification/", include("verification.urls")),

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