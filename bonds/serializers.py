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

        extra_kwargs = {
            "id": {"help_text": "Unique identifier of the bond record."},
            "bond_reference": {"help_text": "Automatically generated unique bond reference."},
            "student": {"help_text": "Student associated with this bond."},
            "status": {"help_text": "Bond status: pending, approved, rejected, or completed."},
            "rejection_reason": {"help_text": "Reason given if the bond is rejected."},
            "created_at": {"help_text": "Date and time the bond was created."},
            "updated_at": {"help_text": "Date and time the bond was last updated."},
            "reviewed_by": {"help_text": "Staff member who reviewed the bond."},
            "reviewed_at": {"help_text": "Date and time the bond was reviewed."},
        }


class BondStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bond
        fields = [
            "status",
            "rejection_reason",
        ]

        extra_kwargs = {
            "status": {"help_text": "New bond status."},
            "rejection_reason": {"help_text": "Required when rejecting a bond."},
        }

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