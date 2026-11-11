from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Agreement
from .validators import validate_signed_pdf


class AgreementSerializer(serializers.ModelSerializer):
    bond_reference = serializers.UUIDField(
        source="bond.bond_reference",
        read_only=True,
        allow_null=True,
    )

    has_student_signed_document = serializers.SerializerMethodField(
        help_text="True once the student has uploaded the signed PDF.",
    )

    has_countersigned_document = serializers.SerializerMethodField(
        help_text="True once the Loan Board Officer has uploaded the final PDF.",
    )

    countersigned_by_username = serializers.SerializerMethodField(
        help_text="Username of the officer who countersigned, if any.",
    )

    class Meta:
        model = Agreement
        fields = [
            "agreement_number",
            "bond",
            "bond_reference",
            "student_id",
            "student_name",
            "programme",
            "academic_year_label",
            "tuition_amount",
            "upkeep_amount",
            "total_amount",
            "loan_reference",
            "agreement_content",
            "generated_pdf",
            "status",
            "generated_at",
            "has_student_signed_document",
            "student_signed_document_sha256",
            "student_signed_at",
            "has_countersigned_document",
            "countersigned_document_sha256",
            "countersigned_by_username",
            "board_countersigned_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "agreement_number",
            "bond",
            "bond_reference",
            "student_id",
            "loan_reference",
            "agreement_content",
            "generated_pdf",
            "status",
            "generated_at",
            "student_signed_document_sha256",
            "student_signed_at",
            "countersigned_document_sha256",
            "board_countersigned_at",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_has_student_signed_document(self, obj):
        return bool(obj.student_signed_document)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_has_countersigned_document(self, obj):
        return bool(obj.countersigned_document)

    @extend_schema_field(OpenApiTypes.STR)
    def get_countersigned_by_username(self, obj):
        return obj.countersigned_by.username if obj.countersigned_by else None


class AgreementGenerateRequestSerializer(serializers.Serializer):
    """
    The student does not supply a student ID or loan reference.
    These are obtained from the authenticated user and approved bond.
    """

    loan_application_id = serializers.IntegerField(required=False)


class AgreementSignedUploadSerializer(serializers.Serializer):
    """Body of the sign and countersign endpoints (multipart/form-data)."""

    signed_document = serializers.FileField(
        validators=[validate_signed_pdf],
        help_text=(
            "The agreement PDF after signing (PDF only, max 10 MB). "
            "Download the document, sign it, then upload it here."
        ),
    )


class ErrorResponseSerializer(serializers.Serializer):
    """Shape of every error response in this app: {"error": "..."}."""

    error = serializers.CharField()


class AgreementActionResponseSerializer(serializers.Serializer):
    """Shape returned by the sign and countersign endpoints."""

    message = serializers.CharField()
    agreement = AgreementSerializer()