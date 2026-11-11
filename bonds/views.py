from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from agreements.models import Agreement
from authentication.models import UserProfile, get_user_role

from .models import AcademicYear, Bond
from .serializers import (
    AcademicYearSerializer,
    BondHistorySerializer,
    BondSerializer,
    BondStatusUpdateSerializer,
)

BONDS_TAG = "Bonds"

UNAUTHENTICATED = OpenApiResponse(
    description="Authentication credentials were not provided or are invalid."
)
NOT_FOUND = OpenApiResponse(
    description="Bond not found, or it does not belong to you."
)


class IsUniversityAdmin(permissions.BasePermission):
    message = "Only university administrators can perform this action."

    def has_permission(self, request, view):
        return (
            get_user_role(request.user)
            == UserProfile.Role.UNIVERSITY_ADMIN
        )


def bonds_for_user(user):
    """Admins and officers see every bond; a student sees only their own."""
    queryset = Bond.objects.select_related(
        "student", "academic_year", "loan_application"
    ).prefetch_related("documents", "agreement")

    role = get_user_role(user)
    if role in (
        UserProfile.Role.UNIVERSITY_ADMIN,
        UserProfile.Role.LOAN_BOARD_OFFICER,
    ):
        return queryset.order_by("-academic_year__label", "-created_at")
    return queryset.filter(student=user).order_by(
        "-academic_year__label", "-created_at"
    )


@extend_schema_view(
    get=extend_schema(
        tags=[BONDS_TAG],
        summary="List bonds",
        description=(
            "Students see only their own bonds, one per academic year. "
            "University administrators and loan board officers see every "
            "bond. Bonds are not created here: verifying the compulsory "
            "documents for an application generates that year's pending "
            "bond and its agreement. A later year never overwrites an "
            "earlier bond or its amount."
        ),
        responses={
            200: BondSerializer(many=True),
            401: UNAUTHENTICATED,
        },
    ),
)
class BondListCreateView(generics.ListAPIView):
    """
    Students can view their own bonds.
    University administrators can view all bonds.
    Bond creation is handled automatically by document verification,
    so this view is list-only (POST returns 405).
    """

    serializer_class = BondSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Bond.objects.none()

        return bonds_for_user(self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=[BONDS_TAG],
        summary="Get one bond",
        description=(
            "Returns a single bond by its numeric ID. Students can open "
            "only their own bond; university administrators can open any."
        ),
        responses={
            200: BondSerializer,
            401: UNAUTHENTICATED,
            404: NOT_FOUND,
        },
    ),
)
class BondHistoryView(generics.ListAPIView):
    """Bond history: academic year, registration, user and amount."""

    serializer_class = BondHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=[BONDS_TAG],
        summary="Bond history",
        description=(
            "History of bonds kept per academic year. Each row is the year, "
            "the student's registration number, the user and the amount "
            "recorded for that year, together with the agreement. Filter "
            "with ?academic_year=2026. Students see their own years; "
            "administrators and officers see every student."
        ),
        responses={200: BondHistorySerializer(many=True), 401: UNAUTHENTICATED},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Bond.objects.none()

        queryset = bonds_for_user(self.request.user)
        label = (self.request.query_params.get("academic_year") or "").strip()
        if label:
            queryset = queryset.filter(academic_year__label=label)
        return queryset


class AcademicYearListCreateView(generics.ListCreateAPIView):
    serializer_class = AcademicYearSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=[BONDS_TAG],
        summary="List or open an academic year",
        description=(
            "Lists academic years. University administrators can create one "
            "by sending {\"label\": \"2027\", \"is_current\": true}. Marking "
            "a year current clears the flag on the others. New loan "
            "applications use the current year when none is sent."
        ),
    )
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AcademicYear.objects.none()
        return AcademicYear.objects.all()

    def perform_create(self, serializer):
        if get_user_role(self.request.user) != UserProfile.Role.UNIVERSITY_ADMIN:
            raise PermissionDenied(
                "Only university administrators can create academic years."
            )
        if serializer.validated_data.get("is_current"):
            AcademicYear.objects.filter(is_current=True).update(is_current=False)
        serializer.save(label=serializer.validated_data["label"].strip())


class BondDetailView(generics.RetrieveAPIView):
    serializer_class = BondSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Bond.objects.none()

        return bonds_for_user(self.request.user)


@extend_schema_view(
    patch=extend_schema(
        tags=[BONDS_TAG],
        summary="Approve or reject a bond",
        description=(
            "University administrators only. Approves or rejects a bond "
            "that is still pending. A rejection must include a reason. "
            "A bond that has already been reviewed cannot be reviewed "
            "again. The reviewer and review time are recorded "
            "automatically."
        ),
        responses={
            200: BondStatusUpdateSerializer,
            400: OpenApiResponse(
                description=(
                    "Invalid status, missing rejection reason, or the bond "
                    "is no longer pending."
                )
            ),
            401: UNAUTHENTICATED,
            403: OpenApiResponse(
                description="Only university administrators can review bonds."
            ),
            404: OpenApiResponse(description="Bond not found."),
        },
    ),
)
class BondStatusUpdateView(generics.UpdateAPIView):
    """
    Only university administrators can approve or reject a bond,
    and only while it is still pending.
    """

    serializer_class = BondStatusUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsUniversityAdmin]
    http_method_names = ["patch", "head", "options"]
    queryset = Bond.objects.all()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)

        with transaction.atomic():
            bond = get_object_or_404(
                Bond.objects.select_for_update(), pk=kwargs["pk"]
            )

            if bond.status != "pending":
                raise ValidationError(
                    {
                        "status": (
                            f"This bond is already {bond.status} "
                            "and cannot be reviewed again."
                        )
                    }
                )

            if request.data.get("status") == "approved" and not (
                Agreement.objects.filter(bond=bond).exists()
            ):
                raise ValidationError(
                    {
                        "status": (
                            "Approve the bond only after its agreement "
                            "has been generated."
                        )
                    }
                )

            serializer = self.get_serializer(
                bond, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(
                reviewed_by=request.user,
                reviewed_at=timezone.now(),
            )

        return Response(serializer.data)