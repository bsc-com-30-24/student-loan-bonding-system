"""
Project-level urls.py (the one next to settings.py, e.g. config/urls.py).
"""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from authentication import views

router = DefaultRouter()
router.register("loans", views.LoanApplicationViewSet, basename="loan")

urlpatterns = [
    path("admin/", admin.site.urls),
    # Loan applications: /api/loans/ and /api/loans/{id}/
    path("api/", include(router.urls)),
    # Authentication
    path("api/register/", views.RegistrationView.as_view(), name="register"),
    path("api/token/", views.RoleTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path(
        "api/password-reset/",
        views.PasswordResetRequestView.as_view(),
        name="password_reset",
    ),
    path(
        "api/password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("api/dashboard/", views.ProtectedDashboardView.as_view(), name="dashboard"),
    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]