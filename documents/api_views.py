import mimetypes

from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, parsers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from .models import Document, Notification
from .notifications import notify_document_rejected
from .services import generate_bond_if_eligible, resolve_loan_application
from .permissions import (
    IsDocumentReviewer,
    IsStudent,
    IsStudentOrDocumentReviewer,
    is_document_reviewer,
)
from .serializers import (
    AdminDocumentSerializer,
    DocumentSerializer,
    DocumentVerificationResponseSerializer,
    DocumentVerificationSerializer,
    StudentNotificationSerializer,
)
from .validators import ALLOWED_FILES_TEXT

STUDENT_TAG = "Documents (Students)"
ADMIN_TAG = "Documents (Admin)"

# Only these are shown inline in the browser; anything else is forced to download.
INLINE_SAFE_TYPES = {"application/pdf", "image/png", "image/jpeg"}

UNAUTHENTICATED = OpenApiResponse(
    description="Not logged in: the Bearer token is missing, invalid or expired."
)
STUDENTS_ONLY = OpenApiResponse(description="Only students can use this endpoint.")
ADMINS_ONLY = OpenApiResponse(
    description="Only university administrators can review documents."
)
DOCUMENT_ID = OpenApiParameter(
    "pk",
    OpenApiTypes.INT,
    OpenApiParameter.PATH,
    description="ID of the document.",
)


@extend_schema_view(
    get=extend_schema(
        tags=[STUDENT_TAG],
        summary="List my documents",
        description=(
            "Returns every document the logged-in student has submitted, newest "
            "first, with its review status (pending, verified or rejected) and "
            "the rejection reason if there is one. Students only see their own "
            "documents."
        ),
        responses={
            200: DocumentSerializer(many=True),
            401: UNAUTHENTICATED,
            403: STUDENTS_ONLY,
        },
    ),
    post=extend_schema(
        tags=[STUDENT_TAG],
        summary="Submit a document",
        description=(
            "Uploads one document for the logged-in student. Send the request as "
            f"multipart/form-data with a document_type and a file ({ALLOWED_FILES_TEXT}). "
            "The document always starts as pending until an administrator "
            "reviews it; the status cannot be set by the student."
        ),
        responses={
            201: DocumentSerializer,
            400: OpenApiResponse(
                description="Invalid document type, or the file is missing, too "
                "large or not a real PDF/JPG/PNG."
            ),
            401: UNAUTHENTICATED,
            403: STUDENTS_ONLY,
        },
    ),
)
class StudentDocumentCreateAPIView(generics.ListCreateAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [IsStudent]
    # A file cannot be sent as JSON, so only form uploads are accepted.
    parser_classes = [
        parsers.MultiPartParser,
        parsers.FormParser,
    ]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Document.objects.none()
        return Document.objects.filter(
            student=self.request.user
        ).order_by("-submitted_at")

    def perform_create(self, serializer):
        requested = serializer.validated_data.pop("loan_application", None)
        if requested is not None and requested.owner_id != self.request.user.id:
            raise ValidationError(
                {"loan_application": "That loan application is not yours."}
            )
        application = requested or resolve_loan_application(self.request.user)
        serializer.save(
            student=self.request.user,
            status="pending",
            loan_application=application,
        )


StudentDocumentListCreateAPIView = StudentDocumentCreateAPIView


@extend_schema(
    tags=[ADMIN_TAG],
    summary="List all submitted documents",
    description=(
        "Returns every document submitted by every student, newest first, "
        "including who submitted it, its status, who reviewed it and a "
        "preview_url for viewing the file. For university administrators."
    ),
    responses={
        200: AdminDocumentSerializer(many=True),
        401: UNAUTHENTICATED,
        403: ADMINS_ONLY,
    },
)
class AdminDocumentListAPIView(generics.ListAPIView):
    serializer_class = AdminDocumentSerializer
    permission_classes = [IsDocumentReviewer]

    def get_queryset(self):
        return Document.objects.select_related(
            "student", "reviewed_by"
        ).order_by("-submitted_at")


class AdminDocumentPreviewAPIView(APIView):
    permission_classes = [IsDocumentReviewer]

    @extend_schema(
        tags=[ADMIN_TAG],
        summary="View an uploaded document",
        description=(
            "Streams the uploaded file so an administrator can inspect it. "
            "PDFs and images open in the browser; any other file type is sent "
            "as a download for safety."
        ),
        parameters=[DOCUMENT_ID],
        responses={
            200: OpenApiTypes.BINARY,
            401: UNAUTHENTICATED,
            403: ADMINS_ONLY,
            404: OpenApiResponse(description="Document or file not found."),
        },
    )
    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        if not document.file:
            raise Http404("No file uploaded for this document.")

        try:
            file_handle = document.file.open("rb")
        except (OSError, ValueError):
            raise Http404("The document file could not be accessed.")

        content_type, _ = mimetypes.guess_type(document.file.name)
        inline = content_type in INLINE_SAFE_TYPES

        return FileResponse(
            file_handle,
            as_attachment=not inline,
            filename=document.file.name.split("/")[-1],
            content_type=content_type if inline else "application/octet-stream",
        )


class DocumentVerificationAPIView(APIView):
    permission_classes = [IsDocumentReviewer]

    @extend_schema(
        tags=[ADMIN_TAG],
        summary="Verify or reject a document",
        description=(
            "Records the administrator's decision on a submitted document. "
            "Send status 'verified' or 'rejected'. A rejection needs a "
            "rejection_reason; the student is then notified in the app and by "
            "email. The reviewer and review time are recorded automatically."
        ),
        parameters=[DOCUMENT_ID],
        request=DocumentVerificationSerializer,
        responses={
            200: DocumentVerificationResponseSerializer,
            400: OpenApiResponse(
                description="Invalid status or missing rejection reason "
                "(body: {\"error\": \"...\"})."
            ),
            401: UNAUTHENTICATED,
            403: ADMINS_ONLY,
            404: OpenApiResponse(description="Document not found."),
        },
    )
    def patch(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        data = request.data if hasattr(request.data, "get") else {}
        new_status = data.get("status")
        reason = data.get("rejection_reason") or ""

        if not isinstance(reason, str):
            return Response(
                {"error": "rejection_reason must be text."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = reason.strip()

        if new_status not in ("verified", "rejected"):
            return Response(
                {"error": "Status must be verified or rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status == "rejected" and not reason:
            return Response(
                {"error": "A rejection reason is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_status = document.status

        with transaction.atomic():
            document.status = new_status
            document.rejection_reason = (
                reason if new_status == "rejected" else ""
            )
            document.reviewed_by = request.user
            document.reviewed_at = timezone.now()

            document.save(
                update_fields=[
                    "status",
                    "rejection_reason",
                    "reviewed_by",
                    "reviewed_at",
                ]
            )

            # Same notice the Django admin sends, so API rejections are not silent.
            if new_status == "rejected" and previous_status != "rejected":
                notify_document_rejected(document)

            bond, bond_created = (None, False)
            if new_status == "verified":
                bond, bond_created = generate_bond_if_eligible(
                    document.student, document
                )

        agreement = getattr(bond, "agreement", None) if bond is not None else None
        return Response({
            "id": document.id,
            "status": document.status,
            "rejection_reason": document.rejection_reason,
            "reviewed_by": request.user.username,
            "reviewed_at": document.reviewed_at,
            "bond_generated": bond_created,
            "bond_id": bond.id if bond_created else None,
            "agreement_generated": bond_created and agreement is not None,
            "agreement_number": (
                str(agreement.agreement_number)
                if bond_created and agreement is not None
                else None
            ),
        })


@extend_schema(
    tags=[STUDENT_TAG],
    summary="List my notifications",
    description=(
        "Returns the logged-in student's notifications, newest first. A "
        "notification is created when one of their documents is rejected and "
        "explains the reason and what to do next."
    ),
    responses={
        200: StudentNotificationSerializer(many=True),
        401: UNAUTHENTICATED,
        403: STUDENTS_ONLY,
    },
)
class StudentNotificationListAPIView(generics.ListAPIView):
    serializer_class = StudentNotificationSerializer
    permission_classes = [IsStudent]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(
            student=self.request.user
        ).select_related("document").order_by("-created_at")


class StudentNotificationMarkReadAPIView(APIView):
    """Marks one of the logged-in student's notifications as read."""

    permission_classes = [IsStudent]

    @extend_schema(
        tags=[STUDENT_TAG],
        summary="Mark a notification as read",
        description=(
            "Marks one of the logged-in student's notifications as read and "
            "returns it. Students can only mark their own notifications; "
            "anyone else's returns 404. Calling it again is harmless."
        ),
        parameters=[
            OpenApiParameter(
                "pk",
                OpenApiTypes.INT,
                OpenApiParameter.PATH,
                description="ID of the notification.",
            )
        ],
        request=None,
        responses={
            200: StudentNotificationSerializer,
            401: UNAUTHENTICATED,
            403: STUDENTS_ONLY,
            404: OpenApiResponse(description="Notification not found."),
        },
    )
    def patch(self, request, *args, **kwargs):
        # The URL parameter is normally "pk"; fall back to the only kwarg so a
        # differently named route parameter still works.
        pk = kwargs.get("pk")
        if pk is None and len(kwargs) == 1:
            pk = next(iter(kwargs.values()))

        notification = get_object_or_404(
            Notification.objects.select_related("document"),
            pk=pk,
            student=request.user,
        )

        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])

        return Response(
            StudentNotificationSerializer(
                notification, context={"request": request}
            ).data
        )

    # Accept POST as well, but keep the Swagger page to a single entry.
    @extend_schema(exclude=True)
    def post(self, request, *args, **kwargs):
        return self.patch(request, *args, **kwargs)


class DocumentDownloadAPIView(APIView):
    """Download a submitted document as a file attachment."""

    permission_classes = [IsStudentOrDocumentReviewer]

    @extend_schema(
        tags=[STUDENT_TAG, ADMIN_TAG],
        summary="Download a submitted document",
        description=(
            "Downloads the uploaded file as an attachment. A student can "
            "download only their own documents (anyone else's returns 404). "
            "University administrators can download any student's document. "
            "Loan board officers and employers are refused."
        ),
        parameters=[DOCUMENT_ID],
        responses={
            200: OpenApiTypes.BINARY,
            401: UNAUTHENTICATED,
            403: OpenApiResponse(
                description="Only students and university administrators can "
                "download documents."
            ),
            404: OpenApiResponse(
                description="Document not found, not yours, or its file is unavailable."
            ),
        },
    )
    def get(self, request, pk):
        if is_document_reviewer(request.user):
            document = get_object_or_404(Document, pk=pk)
        else:
            document = get_object_or_404(Document, pk=pk, student=request.user)

        if not document.file:
            return Response(
                {"error": "No file is attached to this document."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            file_handle = document.file.open("rb")
        except (OSError, ValueError):
            return Response(
                {"error": "The document file is unavailable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        content_type, _ = mimetypes.guess_type(document.file.name)

        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=document.file.name.rsplit("/", 1)[-1],
            content_type=(
                content_type
                if content_type in INLINE_SAFE_TYPES
                else "application/octet-stream"
            ),
        )