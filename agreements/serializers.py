from rest_framework import serializers
from .models import Agreement


class AgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agreement
        fields = [
            "agreement_number",
            "student_id",
            "loan_reference",
            "agreement_content",
            "status",
            "generated_at",
            "student_signed_at",
            "board_countersigned_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "agreement_number",
            "status",
            "generated_at",
            "student_signed_at",
            "board_countersigned_at",
            "created_at",
            "updated_at",
        ]


class AgreementGenerateRequestSerializer(serializers.Serializer):
    student_id = serializers.CharField(max_length=50)
    loan_reference = serializers.CharField(max_length=100)