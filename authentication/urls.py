"""
URL configuration for loan_bonding_auth project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.contrib import admin
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
)

router = DefaultRouter()
router.register("loans", LoanApplicationViewSet, basename="loan-application")

urlpatterns = [
    path("admin/", admin.site.urls),

    # Authentication
    path("api/register/", RegistrationView.as_view(), name="register"),
    path("api/token/", RoleTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path(
        "api/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),

    # Loan applications: /api/loans/ and /api/loans/{id}/
    path("api/", include(router.urls)),

    # API documentation
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
]