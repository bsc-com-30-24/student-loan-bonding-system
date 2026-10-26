from rest_framework import serializers
from .models import Bond


class BondSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bond
        fields = [
            "id",
            "bond_reference",
            "student",
            "status",
            "rejection_reason",
            "created_at",
            "updated_at",
            "reviewed_by",
            "reviewed_at",
        ]

        read_only_fields = [
            "id",
            "bond_reference",
            "student",
            "status",
            "rejection_reason",
            "created_at",
            "updated_at",
            "reviewed_by",
            "reviewed_at",
        ]


class BondStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bond
        fields = [
            "status",
            "rejection_reason",
        ]

    def validate(self, attrs):
        status = attrs.get("status", self.instance.status)
        reason = attrs.get(
            "rejection_reason",
            self.instance.rejection_reason,
        )

        if status == "rejected" and not reason.strip():
            raise serializers.ValidationError({
                "rejection_reason": (
                    "A reason is required when rejecting a bond."
                )
            })

        return attrs