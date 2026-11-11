from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Document, Notification
from .validators import ALLOWED_FILES_TEXT, validate_uploaded_document


def _download_url(document, request):
    """Protected download link for a document (None when there is no file)."""
    if not document.file:
        return None

    url = reverse("document_download_api", kwargs={"pk": document.pk})

    if request:
        return request.build_absolute_uri(url)

    return url


class DocumentSerializer(serializers.ModelSerializer):

    download_url = serializers.SerializerMethodField(
        help_text="Protected URL for downloading the file (needs the Bearer token)."
    )

    class Meta:
        model = Document

        fields = [
            "id",
            "document_type",
            "loan_application",
            "file",
            "download_url",
            "status",
            "rejection_reason",
            "submitted_at",
            "reviewed_at",
        ]

        read_only_fields = [
            "id",
            "status",
            "rejection_reason",
            "submitted_at",
            "reviewed_at",
        ]

        extra_kwargs = {
            "document_type": {
                "help_text": (
                    "Kind of document: student_id, affidavit, guarantor_form, "
                    "other_letter, national_id or guarantor_id."
                ),
            },
            "loan_application": {
                "help_text": (
                    "Loan application this file belongs to. When omitted, the "
                    "student's latest application for the current academic year "
                    "is used, so the tuition on that application is what the "
                    "bond records."
                ),
                "required": False,
                "allow_null": True,
            },
            # Upload-only: the raw storage URL is never returned. Files are
            # reached through the protected download_url instead.
            "file": {
                "write_only": True,
                "help_text": f"The document file ({ALLOWED_FILES_TEXT}).",
            },
            "status": {"help_text": "Review status: pending, verified or rejected."},
            "rejection_reason": {
                "help_text": "Why the document was rejected (empty unless rejected)."
            },
            "submitted_at": {"help_text": "When the document was uploaded."},
            "reviewed_at": {"help_text": "When an administrator reviewed it."},
        }

    def validate_file(self, value):
        try:
            validate_uploaded_document(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages)
        return value

    @extend_schema_field(OpenApiTypes.URI)
    def get_download_url(self, obj):
        return _download_url(obj, self.context.get("request"))


class AdminDocumentSerializer(serializers.ModelSerializer):

    student_username = serializers.CharField(
        source="student.username",
        read_only=True,
        help_text="Username of the student who submitted the document.",
    )

    document_type_display = serializers.CharField(
        source="get_document_type_display",
        read_only=True,
        help_text="Human-readable document type.",
    )

    preview_url = serializers.SerializerMethodField(
        help_text="Protected URL for viewing the file (administrators only)."
    )

    download_url = serializers.SerializerMethodField(
        help_text="Protected URL for downloading the file."
    )

    class Meta:
        model = Document

        fields = [
            "id",
            "student_username",
            "document_type",
            "document_type_display",
            "preview_url",
            "download_url",
            "status",
            "rejection_reason",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
        ]

    @extend_schema_field(OpenApiTypes.URI)
    def get_preview_url(self, obj):

        if not obj.file:
            return None

        request = self.context.get("request")

        url = reverse(
            "admin_document_preview_api",
            kwargs={"pk": obj.pk}
        )

        if request:
            return request.build_absolute_uri(url)

        return url

    @extend_schema_field(OpenApiTypes.URI)
    def get_download_url(self, obj):
        return _download_url(obj, self.context.get("request"))


class StudentNotificationSerializer(serializers.ModelSerializer):

    document_type = serializers.CharField(
        source="document.get_document_type_display",
        read_only=True,
        help_text="Type of the document the notification is about.",
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

        read_only_fields = [
            "id",
            "document",
            "document_type",
            "message",
            "is_read",
            "created_at",
        ]

        extra_kwargs = {
            "document": {"help_text": "ID of the document the notification is about."},
            "message": {"help_text": "What happened and what the student should do."},
            "is_read": {"help_text": "Whether the student has read it."},
            "created_at": {"help_text": "When the notification was created."},
        }


class DocumentVerificationSerializer(serializers.Serializer):
    """Request body of the verification endpoint (also used for Swagger docs)."""

    status = serializers.ChoiceField(
        choices=["verified", "rejected"],
        help_text="The decision for the submitted document.",
    )
    rejection_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Required when status is rejected. Shown to the student.",
    )


class DocumentVerificationResponseSerializer(serializers.Serializer):
    """Response body of the verification endpoint (Swagger docs only)."""

    id = serializers.IntegerField()
    status = serializers.CharField()
    rejection_reason = serializers.CharField()
    reviewed_by = serializers.CharField(help_text="Username of the reviewer.")
    reviewed_at = serializers.DateTimeField()
    bond_generated = serializers.BooleanField(
        help_text=(
            "True when this verification completed the compulsory documents "
            "and a new bond plus agreement were created for that academic year."
        ),
    )
    bond_id = serializers.IntegerField(allow_null=True)
    agreement_generated = serializers.BooleanField()
    agreement_number = serializers.UUIDField(allow_null=True)