import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import generics, serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import LoanApplication, PasswordResetOTP, UserProfile, get_user_role
from .permissions import ALL_ROLES, HasRolePermission
from .serializers import (
    LoanApplicationReviewSerializer,
    LoanApplicationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
    RoleTokenObtainPairSerializer,
)

User = get_user_model()

DetailSerializer = inline_serializer(
    name="DetailResponse",
    fields={"detail": serializers.CharField()},
)

DashboardSerializer = inline_serializer(
    name="DashboardResponse",
    fields={
        "message": serializers.CharField(),
        "user_id": serializers.IntegerField(),
        "role": serializers.CharField(),
    },
)


class RegistrationView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: DetailSerializer},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        users = User.objects.filter(
            email__iexact=serializer.validated_data["email"],
            is_active=True,
        )

        for user in users:
            otp = str(secrets.randbelow(900000) + 100000)

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
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={
            200: DetailSerializer,
            400: OpenApiResponse(description="Invalid OTP, email or password."),
        },
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        serializer.validated_data["otp_record"].delete()

        return Response({"detail": "Password has been reset successfully."})


class RoleTokenObtainPairView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer


class ProtectedDashboardView(APIView):
    permission_classes = [IsAuthenticated, HasRolePermission]
    allowed_roles = ALL_ROLES
    serializer_class = DashboardSerializer

    @extend_schema(responses={200: DashboardSerializer})
    def get(self, request):
        return Response(
            {
                "message": f"Hello, {request.user.username}! You are authenticated.",
                "user_id": request.user.id,
                "role": get_user_role(request.user),
            }
        )


class LoanApplicationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasRolePermission]
    queryset = LoanApplication.objects.none()  # lets Swagger infer the {id} type

    def get_queryset(self):
        # drf-spectacular calls this with an anonymous user while building the schema
        if getattr(self, "swagger_fake_view", False):
            return LoanApplication.objects.none()

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
        if getattr(self, "swagger_fake_view", False):
            return LoanApplicationSerializer
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