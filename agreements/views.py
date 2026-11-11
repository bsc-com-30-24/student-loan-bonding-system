import hashlib

from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)

from rest_framework import generics, parsers, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import UserProfile, get_user_role

from .models import Agreement
from .serializers import (
    AgreementActionResponseSerializer,
    AgreementSerializer,
    AgreementSignedUploadSerializer,
    ErrorResponseSerializer,
)


AGREEMENT_NUMBER_PARAM = OpenApiParameter(
    name="agreement_number",
    type=OpenApiTypes.UUID,
    location=OpenApiParameter.PATH,
    description="UUID of the agreement.",
)

# download ?version=...  ->  (model field, file name)
DOWNLOAD_VERSIONS = {
    "original": ("generated_pdf", "agreement_{number}.pdf"),
    "student_signed": (
        "student_signed_document",
        "agreement_{number}_student_signed.pdf",
    ),
    "countersigned": (
        "countersigned_document",
        "agreement_{number}_countersigned.pdf",
    ),
}

VERSION_PARAM = OpenApiParameter(
    name="version",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    enum=list(DOWNLOAD_VERSIONS),
    description=(
        "Which copy to download: 'original' (unsigned, the default), "
        "'student_signed' (after the student uploaded it) or "
        "'countersigned' (the final copy after the officer uploaded it)."
    ),
)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def get_registration_number(user):
    """Return the student's registration number, or None if not set."""
    profile = getattr(user, "profile", None)
    return getattr(profile, "student_registration_number", None) or None


def get_student_identifiers(user):
    """All values an Agreement.student_id may hold for this user."""
    identifiers = [str(user.pk), user.get_username()]
    registration_number = get_registration_number(user)
    if registration_number:
        identifiers.append(str(registration_number))
    return identifiers


def agreements_for_user(user):
    """Students see their own agreements; admins and officers see all."""
    role = get_user_role(user)

    if role == UserProfile.Role.STUDENT:
        return Agreement.objects.filter(
            student_id__in=get_student_identifiers(user)
        ).order_by("-generated_at")

    if role in (
        UserProfile.Role.UNIVERSITY_ADMIN,
        UserProfile.Role.LOAN_BOARD_OFFICER,
    ):
        return Agreement.objects.all().order_by("-generated_at")

    return Agreement.objects.none()


def sha256_of(uploaded_file):
    """SHA-256 hex digest of an uploaded file (leaves it rewound)."""
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


# --------------------------------------------------
# ROLE PERMISSIONS
# --------------------------------------------------

class IsStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        return get_user_role(request.user) == UserProfile.Role.STUDENT


class IsUniversityAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            get_user_role(request.user)
            == UserProfile.Role.UNIVERSITY_ADMIN
        )


class IsLoanBoardOfficer(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            get_user_role(request.user)
            == UserProfile.Role.LOAN_BOARD_OFFICER
        )


# --------------------------------------------------
# AGREEMENT LIST
# --------------------------------------------------

@extend_schema_view(
    get=extend_schema(
        summary="List agreements",
        description=(
            "Students see their own agreements. University administrators "
            "and Loan Board Officers can see all agreements."
        ),
        tags=["Agreements"],
    )
)
class AgreementListView(generics.ListAPIView):
    serializer_class = AgreementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return agreements_for_user(self.request.user)


# --------------------------------------------------
# AGREEMENT DETAIL
# --------------------------------------------------

@extend_schema_view(
    get=extend_schema(
        summary="Retrieve an agreement",
        parameters=[AGREEMENT_NUMBER_PARAM],
        tags=["Agreements"],
    )
)
class AgreementDetailView(generics.RetrieveAPIView):
    serializer_class = AgreementSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "agreement_number"

    def get_queryset(self):
        return agreements_for_user(self.request.user)


# --------------------------------------------------
# GENERATE AGREEMENT
# --------------------------------------------------

class AgreementGenerateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @extend_schema(
        request=None,
        responses={
            201: AgreementSerializer,
            400: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
        summary="Agreements are generated from verified documents",
        description=(
            "Agreements are created automatically when a student's "
            "compulsory documents for an academic year are verified. "
            "The bond stays pending until a university administrator "
            "approves it. This endpoint does not create another agreement."
        ),
        tags=["Agreements"],
    )
    def post(self, request):
        return Response(
            {
                "error": (
                    "Agreements are generated automatically when the "
                    "compulsory documents for an academic year are verified. "
                    "Download the template, then a university administrator "
                    "approves the pending bond."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


# --------------------------------------------------
# STUDENT UPLOADS THE SIGNED AGREEMENT
# --------------------------------------------------

class AgreementSignView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    @extend_schema(
        request=AgreementSignedUploadSerializer,
        parameters=[AGREEMENT_NUMBER_PARAM],
        responses={
            200: AgreementActionResponseSerializer,
            400: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        summary="Student uploads the signed agreement",
        description=(
            "Step 1 of signing: download the agreement with "
            "GET /download/ (version 'original'), sign it, then upload the "
            "signed PDF here as multipart/form-data in the 'signed_document' "
            "field. Only the student who owns the agreement can do this, "
            "once, while it is GENERATED or PENDING_SIGNATURE. The agreement "
            "then becomes SIGNED and waits for the Loan Board Officer."
        ),
        tags=["Agreements"],
    )
    def post(self, request, agreement_number):
        with transaction.atomic():
            agreement = get_object_or_404(
                Agreement.objects.select_for_update(),
                agreement_number=agreement_number,
            )

            if agreement.student_id not in get_student_identifiers(
                request.user
            ):
                return Response(
                    {
                        "error": (
                            "You are not authorized to sign "
                            "this agreement."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            if agreement.status not in (
                Agreement.Status.GENERATED,
                Agreement.Status.PENDING_SIGNATURE,
            ):
                return Response(
                    {
                        "error": (
                            "This agreement cannot be signed "
                            "in its current status."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = AgreementSignedUploadSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            uploaded = serializer.validated_data["signed_document"]

            agreement.student_signed_document_sha256 = sha256_of(uploaded)
            agreement.student_signed_document.save(
                f"agreement_{agreement.agreement_number}_student_signed.pdf",
                uploaded,
                save=False,
            )
            agreement.status = Agreement.Status.SIGNED
            agreement.student_signed_at = timezone.now()
            agreement.save(
                update_fields=[
                    "student_signed_document",
                    "student_signed_document_sha256",
                    "status",
                    "student_signed_at",
                    "updated_at",
                ]
            )

        return Response(
            {
                "message": "Signed agreement uploaded successfully.",
                "agreement": AgreementSerializer(agreement).data,
            },
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------
# LOAN BOARD OFFICER UPLOADS THE COUNTERSIGNED AGREEMENT
# --------------------------------------------------

class AgreementCountersignView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsLoanBoardOfficer]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    @extend_schema(
        request=AgreementSignedUploadSerializer,
        parameters=[AGREEMENT_NUMBER_PARAM],
        responses={
            200: AgreementActionResponseSerializer,
            400: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        summary="Loan Board Officer uploads the countersigned agreement",
        description=(
            "Step 2 of signing: download the student-signed copy with "
            "GET /download/?version=student_signed, countersign it, then "
            "upload the final PDF here as multipart/form-data in the "
            "'signed_document' field. Only a Loan Board Officer can do "
            "this, and only after the student has uploaded their signed "
            "copy. The agreement then becomes COUNTERSIGNED."
        ),
        tags=["Agreements"],
    )
    def post(self, request, agreement_number):
        with transaction.atomic():
            agreement = get_object_or_404(
                Agreement.objects.select_for_update(),
                agreement_number=agreement_number,
            )

            if (
                agreement.status != Agreement.Status.SIGNED
                or not agreement.student_signed_document
            ):
                return Response(
                    {
                        "error": (
                            "Only agreements with an uploaded "
                            "student-signed copy can be countersigned."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = AgreementSignedUploadSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            uploaded = serializer.validated_data["signed_document"]

            agreement.countersigned_document_sha256 = sha256_of(uploaded)
            agreement.countersigned_document.save(
                f"agreement_{agreement.agreement_number}_countersigned.pdf",
                uploaded,
                save=False,
            )
            agreement.countersigned_by = request.user
            agreement.status = Agreement.Status.COUNTERSIGNED
            agreement.board_countersigned_at = timezone.now()
            agreement.save(
                update_fields=[
                    "countersigned_document",
                    "countersigned_document_sha256",
                    "countersigned_by",
                    "status",
                    "board_countersigned_at",
                    "updated_at",
                ]
            )

        return Response(
            {
                "message": "Countersigned agreement uploaded successfully.",
                "agreement": AgreementSerializer(agreement).data,
            },
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------
# DOWNLOAD AGREEMENT PDF (original, student-signed or countersigned)
# --------------------------------------------------

class AgreementPDFDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[AGREEMENT_NUMBER_PARAM, VERSION_PARAM],
        responses={
            200: OpenApiTypes.BINARY,
            400: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        summary="Download an agreement PDF",
        description=(
            "Students can download their own agreements. University "
            "administrators and Loan Board Officers can download all "
            "agreements. Use the 'version' query parameter to choose the "
            "copy: 'original' (default) is what the student signs, "
            "'student_signed' is what the officer countersigns, and "
            "'countersigned' is the final copy."
        ),
        tags=["Agreements"],
    )
    def get(self, request, agreement_number):
        agreement = get_object_or_404(
            Agreement, agreement_number=agreement_number
        )

        role = get_user_role(request.user)

        if role == UserProfile.Role.STUDENT:
            if agreement.student_id not in get_student_identifiers(
                request.user
            ):
                return Response(
                    {
                        "error": (
                            "You are not authorized to download "
                            "this agreement."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif role not in (
            UserProfile.Role.UNIVERSITY_ADMIN,
            UserProfile.Role.LOAN_BOARD_OFFICER,
        ):
            return Response(
                {"error": "You are not authorized to download agreements."},
                status=status.HTTP_403_FORBIDDEN,
            )

        version = request.query_params.get("version", "original")

        if version not in DOWNLOAD_VERSIONS:
            return Response(
                {
                    "error": (
                        "version must be one of: "
                        + ", ".join(DOWNLOAD_VERSIONS)
                        + "."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        field_name, filename_template = DOWNLOAD_VERSIONS[version]
        stored_file = getattr(agreement, field_name)

        if not stored_file:
            return Response(
                {
                    "error": (
                        f"The {version.replace('_', ' ')} copy "
                        "is not available yet."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            pdf_file = stored_file.open("rb")
        except (OSError, ValueError):
            return Response(
                {"error": "The agreement PDF could not be accessed."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return FileResponse(
            pdf_file,
            as_attachment=True,
            filename=filename_template.format(
                number=agreement.agreement_number
            ),
            content_type="application/pdf",
        )