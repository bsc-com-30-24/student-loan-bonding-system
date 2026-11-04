from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

import random
from rest_framework import generics, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from drf_spectacular.utils import extend_schema

from .models import LoanApplication, UserProfile, get_user_role, PasswordResetOTP
from .permissions import HasRolePermission
from .serializers import (
    LoanApplicationReviewSerializer,
    LoanApplicationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
    RoleTokenObtainPairSerializer,
)

User = get_user_model()


@extend_schema(
    tags=["Authentication"],
    summary="Register User",
    description="Creates a new user account and assigns a role."
)
class RegistrationView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]


@extend_schema(
    tags=["Authentication"],
    summary="Request Password Reset",
    description="Sends a one-time password (OTP) to the user's registered email."
)
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: dict}
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        users = User.objects.filter(
            email__iexact=serializer.validated_data["email"],
            is_active=True,
        )

        for user in users:
            otp = str(random.randint(100000, 999999))

            PasswordResetOTP.objects.filter(email=user.email).delete()

            PasswordResetOTP.objects.create(email=user.email, otp=otp)

            send_mail(
                subject="Password Reset OTP",
                message=f"Your OTP is: {otp}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )

        return Response(
            {"detail": "If an account exists for this email, an OTP has been sent."}
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="Confirm Password Reset",
        description="Verifies OTP and resets the password."
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        serializer.validated_data["otp_record"].delete()

        return Response({"detail": "Password has been reset successfully."})


@extend_schema(
    tags=["Authentication"],
    summary="Login",
    description="Authenticates a user and returns JWT access and refresh tokens."
)
class RoleTokenObtainPairView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer


@extend_schema(
    tags=["Authentication"],
    description="Manage loan applications.",
    exclude=True,
)
class LoanApplicationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasRolePermission]

    def get_queryset(self):
        role = get_user_role(self.request.user)
        if role in {
            UserProfile.Role.UNIVERSITY_ADMIN,
            UserProfile.Role.LOAN_BOARD_OFFICER,
        }:
            return LoanApplication.objects.all()
        if role == UserProfile.Role.STUDENT:
            return LoanApplication.objects.filter(owner=self.request.user)
        return LoanApplication.objects.none()

    def get_serializer_class(self):
        if (
            self.action in {"update", "partial_update"}
            and get_user_role(self.request.user) == UserProfile.Role.LOAN_BOARD_OFFICER
        ):
            return LoanApplicationReviewSerializer
        return LoanApplicationSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        if (
            get_user_role(self.request.user) == UserProfile.Role.STUDENT
            and self.get_object().status != LoanApplication.Status.PENDING
        ):
            raise PermissionDenied("Only pending applications can be edited.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != LoanApplication.Status.PENDING:
            raise PermissionDenied("Only pending applications can be deleted.")
        instance.delete()