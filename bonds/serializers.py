from rest_framework import serializers

from .models import AcademicYear, Bond


class BondSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(
        source="student.username",
        read_only=True,
        help_text="Username of the student the bond belongs to.",
    )
    academic_year = serializers.CharField(
        source="academic_year.label",
        read_only=True,
        allow_null=True,
        help_text="Academic year this bond belongs to, for example 2026.",
    )
    agreement_number = serializers.SerializerMethodField()
    document_ids = serializers.PrimaryKeyRelatedField(
        source="documents",
        many=True,
        read_only=True,
    )

    class Meta:
        model = Bond

        fields = [
            "id",
            "bond_reference",
            "student",
            "student_username",
            "registration_number",
            "academic_year",
            "loan_application",
            "tuition_amount",
            "upkeep_amount",
            "amount",
            "document_ids",
            "agreement_number",
            "status",
            "rejection_reason",
            "created_at",
            "updated_at",
            "reviewed_by",
            "reviewed_at",
        ]

        read_only_fields = fields

        extra_kwargs = {
            "id": {"help_text": "Numeric ID of the bond."},
            "bond_reference": {
                "help_text": "Unique public reference (UUID) of the bond.",
            },
            "student": {
                "help_text": "ID of the student the bond belongs to.",
            },
            "registration_number": {
                "help_text": "Registration number recorded on this bond.",
            },
            "loan_application": {
                "help_text": "Application whose tuition and upkeep this bond keeps.",
            },
            "tuition_amount": {
                "help_text": "Tuition fees for this academic year. Not changed by later years.",
            },
            "upkeep_amount": {
                "help_text": "Upkeep amount for this academic year.",
            },
            "amount": {
                "help_text": "Tuition plus upkeep, stored with this year's bond.",
            },
            "status": {
                "help_text": (
                    "Bond status: pending, approved, rejected or completed."
                ),
            },
            "rejection_reason": {
                "help_text": "Why the bond was rejected (empty otherwise).",
            },
            "created_at": {
                "help_text": "When the bond was generated.",
            },
            "updated_at": {
                "help_text": "When the bond was last changed.",
            },
            "reviewed_by": {
                "help_text": "ID of the administrator who reviewed the bond.",
            },
            "reviewed_at": {
                "help_text": "When the bond was approved or rejected.",
            },
        }

    def get_agreement_number(self, obj):
        agreement = getattr(obj, "agreement", None)
        if agreement is None:
            return None
        return str(agreement.agreement_number)


class BondHistorySerializer(serializers.ModelSerializer):
    """One row of bond history: year, registration, user and amount."""

    academic_year = serializers.CharField(
        source="academic_year.label",
        read_only=True,
        allow_null=True,
    )
    user = serializers.CharField(source="student.username", read_only=True)
    agreement_number = serializers.SerializerMethodField()
    agreement_status = serializers.SerializerMethodField()

    class Meta:
        model = Bond
        fields = [
            "id",
            "academic_year",
            "registration_number",
            "user",
            "amount",
            "tuition_amount",
            "upkeep_amount",
            "status",
            "agreement_number",
            "agreement_status",
            "created_at",
        ]

    def get_agreement_number(self, obj):
        agreement = getattr(obj, "agreement", None)
        if agreement is None:
            return None
        return str(agreement.agreement_number)

    def get_agreement_status(self, obj):
        agreement = getattr(obj, "agreement", None)
        if agreement is None:
            return None
        return agreement.status


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "label", "is_current"]


class BondStatusUpdateSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(
        choices=["approved", "rejected"],
        help_text="The decision for the bond: approved or rejected.",
    )

    class Meta:
        model = Bond

        fields = [
            "status",
            "rejection_reason",
        ]

        extra_kwargs = {
            "rejection_reason": {
                "help_text": (
                    "Required when status is rejected. "
                    "Ignored (cleared) when the bond is approved."
                ),
            },
        }

    def validate(self, attrs):
        if self.instance is None or self.instance.status != "pending":
            raise serializers.ValidationError(
                "Only pending bonds can be reviewed."
            )

        new_status = attrs.get("status")

        if new_status is None:
            raise serializers.ValidationError({
                "status": "This field is required."
            })

        if new_status not in ("approved", "rejected"):
            raise serializers.ValidationError({
                "status": "A bond can only be approved or rejected."
            })

        reason = attrs.get(
            "rejection_reason",
            self.instance.rejection_reason,
        )

        if new_status == "rejected":
            if not reason or not reason.strip():
                raise serializers.ValidationError({
                    "rejection_reason": (
                        "A rejection reason is required."
                    )
                })
            attrs["rejection_reason"] = reason.strip()

        if new_status == "approved":
            attrs["rejection_reason"] = ""

        return attrs