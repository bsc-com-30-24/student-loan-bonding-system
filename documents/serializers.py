from rest_framework import serializers
from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = (
            "id",
            "document_type",
            "file",
            "status",
            "rejection_reason",
            "submitted_at",
            "reviewed_at",
        )
        read_only_fields = (
            "id",
            "status",
            "rejection_reason",
            "submitted_at",
            "reviewed_at",
        )