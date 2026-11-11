import logging
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, viewsets
from rest_framework.filters import SearchFilter
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .access import IsStudentRole, IsUniversityAdminOrBoardOfficer
from .models import (
    LoanApplication,
    PasswordResetOTP,
    StudentDetail,
    UserProfile,
    get_user_role,
)
from .permissions import HasRolePermission
from .serializers import (
    DetailSerializer,
    LoanApplicationReviewSerializer,
    LoanApplicationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
    RoleTokenObtainPairSerializer,
    StudentDetailSerializer,
)
from .throttles import (
    PasswordResetConfirmThrottle,
    PasswordResetRequestThrottle,
    RegistrationThrottle,
)

User = get_user_model()
logger = logging.getLogger(__name__)


@extend_schema(
    tags=["Authentication"],
    summary="Register User",
    description="Creates a new student account with a profile.",
)
class RegistrationView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]
    authentication_classes = []  # ignore stale/invalid Bearer tokens
    throttle_classes = [RegistrationThrottle]


@extend_schema(
    tags=["Authentication"],
    summary="Request Password Reset",
    description="Sends a one-time password (OTP) to the user's registered email.",
)
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetRequestThrottle]

    @extend_schema(request=PasswordResetRequestSerializer, responses={200: DetailSerializer})
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = (
            User.objects.filter(
                email__iexact=serializer.validated_data["email"].strip(),
                is_active=True,
            )
            .order_by("id")
            .first()
        )

        if user:
            otp = f"{secrets.randbelow(1_000_000):06d}"  # keeps leading zeros
            with transaction.atomic():
                PasswordResetOTP.objects.filter(email__iexact=user.email).delete()
                PasswordResetOTP.objects.create(email=user.email, otp=otp)
            try:
                send_mail(
                    subject="Password Reset OTP",
                    message=f"Your OTP is: {otp}. It expires in 10 minutes.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                )
            except Exception:
                # Never reveal mail failures: the response must look identical.
                logger.exception("Failed to send password reset email")

        return Response(
            {"detail": "If an account exists for this email, an OTP has been sent."}
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetConfirmThrottle]

    @extend_schema(
        tags=["Authentication"],
        summary="Confirm Password Reset",
        description="Verifies OTP and resets the password.",
        request=PasswordResetConfirmSerializer,
        responses={200: DetailSerializer},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        with transaction.atomic():
            user.set_password(serializer.validated_data["new_password"])
            user.save(update_fields=["password"])
            # Single use: remove every OTP for this email.
            PasswordResetOTP.objects.filter(email__iexact=user.email).delete()

        return Response({"detail": "Password has been reset successfully."})


@extend_schema(
    tags=["Authentication"],
    summary="Login",
    description="Authenticates a user and returns JWT access and refresh tokens.",
)
class RoleTokenObtainPairView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List loan applications",
        description=(
            "Students see only their own applications. University administrators "
            "and loan board officers see every application. Employers are refused."
        ),
    ),
    retrieve=extend_schema(
        summary="Get one loan application",
        description=(
            "Returns a single application with its loan_reference, amounts and "
            "status. Students can only open their own; others get 404."
        ),
    ),
    create=extend_schema(
        summary="Submit a loan application",
        description=(
            "Students only. Send tuition_amount and upkeep_amount (neither can be "
            "negative and the total must be above zero). The owner is taken from "
            "the logged-in user, the status always starts as pending and the "
            "loan_reference (e.g. SLBS-2026-00001) is generated automatically."
        ),
    ),
    update=extend_schema(
        summary="Update a loan application",
        description=(
            "Students can change the amounts of their own pending applications. "
            "Loan board officers can only change the status "
            "(pending, approved or rejected); the amounts stay locked for them."
        ),
    ),
    partial_update=extend_schema(
        summary="Partially update a loan application",
        description=(
            "Same rules as a full update, but only the fields sent are changed. "
            "A loan board officer sends just {\"status\": \"approved\"} or "
            "{\"status\": \"rejected\"} to record a decision."
        ),
    ),
    destroy=extend_schema(
        summary="Delete a loan application",
        description=(
            "Students only, and only while the application is still pending. "
            "Approved or rejected applications cannot be deleted."
        ),
    ),
)
@extend_schema(tags=["Authentication"])
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
            and serializer.instance.status != LoanApplication.Status.PENDING
        ):
            raise PermissionDenied("Only pending applications can be edited.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != LoanApplication.Status.PENDING:
            raise PermissionDenied("Only pending applications can be deleted.")
        instance.delete()


@extend_schema_view(
    get=extend_schema(
        tags=["Authentication"],
        summary="Get my student details",
        description=(
            "Returns the logged-in student's details: name, programme, year of "
            "study, phone number and registration number. An empty record is "
            "created the first time. is_complete shows whether everything an "
            "agreement needs is filled in."
        ),
    ),
    put=extend_schema(
        tags=["Authentication"],
        summary="Replace my student details",
        description="Students only. Sets all the editable details at once.",
    ),
    patch=extend_schema(
        tags=["Authentication"],
        summary="Update my student details",
        description=(
            "Students only. Send only the fields to change, for example "
            '{"programme": "BSc Computer Science", "year_of_study": 2}.'
        ),
    ),
)
class StudentDetailMeView(generics.RetrieveUpdateAPIView):
    serializer_class = StudentDetailSerializer
    permission_classes = [IsStudentRole]

    def get_object(self):
        detail, _ = StudentDetail.objects.select_related("user").get_or_create(
            user=self.request.user
        )
        return detail


@extend_schema_view(
    list=extend_schema(
        tags=["Authentication"],
        summary="List students",
        description=(
            "University administrators and loan board officers only. Returns "
            "every student's details. Use ?search= to find a student by name, "
            "username, email or registration number."
        ),
    ),
    retrieve=extend_schema(
        tags=["Authentication"],
        summary="Get one student's details",
        description=(
            "University administrators and loan board officers only. "
            "Read-only: students edit their own details through /api/students/me/."
        ),
    ),
)
class StudentDetailViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudentDetailSerializer
    permission_classes = [IsUniversityAdminOrBoardOfficer]
    queryset = StudentDetail.objects.select_related("user", "user__profile").order_by(
        "full_name", "user__username"
    )
    filter_backends = [SearchFilter]
    search_fields = [
        "full_name",
        "user__username",
        "user__email",
        "user__profile__student_registration_number",
    ]
    lookup_value_regex = r"\d+"  # keeps /students/me/ from matching a detail id