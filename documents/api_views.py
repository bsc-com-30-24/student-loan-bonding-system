
import mimetypes
import os

from django.conf import settings
from django.core.mail import send_mail
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import (
    generics,
    permissions,
    parsers,
    serializers,
    status,
)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from drf_spectacular.utils import extend_schema, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from .models import Document, Notification

from .serializers import (
    DocumentSerializer,
    AdminDocumentSerializer,
)


class StudentDocumentCreateAPIView(generics.CreateAPIView):

    serializer_class = DocumentSerializer

    permission_classes = [
        permissions.IsAuthenticated
    ]

    parser_classes = [
        parsers.MultiPartParser,
        parsers.FormParser,
    ]

    def create(self, request, *args, **kwargs):

        if not request.user.is_active or request.user.is_staff:
            raise PermissionDenied(
                "Only active student users can submit documents."
            )

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):

        serializer.save(
            student=self.request.user,
            status="pending",
        )


class AdminDocumentListAPIView(generics.ListAPIView):

    serializer_class = AdminDocumentSerializer

    permission_classes = [
        permissions.IsAdminUser
    ]

    queryset = Document.objects.select_related(
        "student",
        "reviewed_by",
    ).all().order_by("-submitted_at")


class AdminDocumentPreviewAPIView(APIView):

    permission_classes = [
        permissions.IsAdminUser
    ]

    def get(self, request, pk):

        document = get_object_or_404(
            Document,
            pk=pk
        )

        if not document.file:
            return Response(
                {"error": "This document has no uploaded file."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            uploaded_file = document.file.open("rb")
        except (FileNotFoundError, OSError):
            return Response(
                {"error": "The uploaded file could not be found."},
                status=status.HTTP_404_NOT_FOUND
            )

        content_type, _ = mimetypes.guess_type(
            document.file.name
        )

        response = FileResponse(
            uploaded_file,
            content_type=content_type or "application/octet-stream"
        )

        filename = os.path.basename(document.file.name)

        response["Content-Disposition"] = (
            f'inline; filename="{filename}"'
        )

        return response


class DocumentVerificationAPIView(APIView):

    permission_classes = [
        permissions.IsAdminUser
    ]

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["verified", "rejected"]
                    },
                    "rejection_reason": {
                        "type": "string"
                    }
                },
                "required": ["status"]
            }
        },
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiResponse(
                description="Invalid status or missing rejection reason."
            ),
            403: OpenApiResponse(
                description="Administrator permission required."
            ),
            404: OpenApiResponse(
                description="Document not found."
            ),
        }
    )
    def patch(self, request, pk):

        document = get_object_or_404(
            Document,
            pk=pk
        )

        new_status = request.data.get("status")

        reason = (
            request.data.get("rejection_reason") or ""
        ).strip()

        if new_status not in ["verified", "rejected"]:
            return Response(
                {"error": "Status must be verified or rejected."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_status == "rejected" and not reason:
            return Response(
                {"error": "A rejection reason is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = document.status

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

        if new_status == "rejected" and old_status != "rejected":

            message = (
                f"Your {document.get_document_type_display()} "
                f"document has been rejected. "
                f"Reason: {document.rejection_reason}. "
                "Please correct the issue and submit the document again."
            )

            Notification.objects.create(
                student=document.student,
                document=document,
                message=message,
            )

            if document.student.email:
                send_mail(
                    subject="Your document has been rejected",
                    message=(
                        f"Hello {document.student.username},\n\n"
                        f"{message}\n\n"
                        "Student Loan Bonding System"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[document.student.email],
                    fail_silently=True,
                )

        return Response(
            {
                "message": "Document review completed successfully.",
                "id": document.id,
                "status": document.status,
                "rejection_reason": document.rejection_reason,
                "reviewed_by": request.user.username,
                "reviewed_at": document.reviewed_at,
            },
            status=status.HTTP_200_OK
        )


class StudentNotificationSerializer(serializers.ModelSerializer):

    document_type = serializers.CharField(
        source="document.get_document_type_display",
        read_only=True
    )

    class Meta:
        model = Notification

        fields = [
            "id",
            "document",
            "document_type",
            "message",
            "is_read",
            "created_at",
        ]

        read_only_fields = fields


class StudentNotificationListAPIView(generics.ListAPIView):

    serializer_class = StudentNotificationSerializer

    permission_classes = [
        permissions.IsAuthenticated
    ]

    def get_queryset(self):

        if self.request.user.is_staff:
            return Notification.objects.none()

        return Notification.objects.filter(
            student=self.request.user
        ).select_related(
            "document"
        ).order_by("-created_at")
