"""
URL configuration for loan_bonding_auth project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework.permissions import AllowAny
from  rest_framework_simplejwt.views import (
    TokenRefreshView,
)

from authentication.views import (
    LoanApplicationViewSet,
    PasswordResetConfirmView,
    PasswordResetRequestView,
   # ProtectedDashboardView,
    RegistrationView,
    RoleTokenObtainPairView,
)

router = DefaultRouter()
router.register('loans', LoanApplicationViewSet, basename='loan-application')

urlpatterns = [
    path('admin/', admin.site.urls),

    # JWT Authentication endpoints
    path('api/register/', RegistrationView.as_view(), name='register'),
    path('api/password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('api/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('api/token/', RoleTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
   # path('api/protected/', ProtectedDashboardView.as_view(), name='protected_data'),
   # path('api/dashboard/', ProtectedDashboardView.as_view(), name='protected_dashboard'),
    path('api/', include(router.urls)),
    path('api/schema/', SpectacularAPIView.as_view(permission_classes=[AllowAny]), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(permission_classes=[AllowAny], url_name='schema'), name='swagger-ui'),

]
