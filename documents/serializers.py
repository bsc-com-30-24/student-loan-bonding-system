
from django.urls import reverse
from rest_framework import serializers

from .models import Document, Notification


class DocumentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Document

        fields = [
            "id",
            "document_type",
            "file",
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


class AdminDocumentSerializer(serializers.ModelSerializer):

    student_username = serializers.CharField(
        source="student.username",
        read_only=True
    )

    document_type_display = serializers.CharField(
        source="get_document_type_display",
        read_only=True
    )

    preview_url = serializers.SerializerMethodField()

    class Meta:
        model = Document

        fields = [
            "id",
            "student_username",
            "document_type",
            "document_type_display",
            "file",
            "preview_url",
            "status",
            "rejection_reason",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
        ]

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

        read_only_fields = [
            "id",
            "document",
            "document_type",
            "message",
            "is_read",
            "created_at",
        ]
