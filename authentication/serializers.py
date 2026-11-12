import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import (
    LoanApplication,
    PasswordResetOTP,
    StudentDetail,
    UserProfile,
    get_user_role,
    phone_validator,
)

User = get_user_model()

OTP_TTL = timedelta(minutes=10)
MAX_OTP_ATTEMPTS = 5


class DetailSerializer(serializers.Serializer):
    """Shape of simple {"detail": "..."} responses (used for Swagger docs)."""

    detail = serializers.CharField()


class LoanApplicationSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()
    academic_year = serializers.CharField(
        required=False,
        allow_blank=False,
        help_text=(
            "Academic year for these fees, for example 2026 or 2025/2026. "
            "Defaults to the current year. One application per student per year."
        ),
    )

    class Meta:
        model = LoanApplication
        fields = [
            "id",
            "loan_reference",
            "owner",
            "academic_year",
            "tuition_amount",
            "upkeep_amount",
            "amount",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "loan_reference",
            "owner",
            "amount",
            "status",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.DecimalField(max_digits=13, decimal_places=2))
    def get_amount(self, obj):
        return obj.get_total_amount()

    def validate(self, attrs):
        # On PATCH, fall back to the stored values for fields that were not sent.
        tuition = attrs.get("tuition_amount", getattr(self.instance, "tuition_amount", 0))
        upkeep = attrs.get("upkeep_amount", getattr(self.instance, "upkeep_amount", 0))
        if tuition + upkeep <= 0:
            raise serializers.ValidationError(
                "The combined loan amount must be greater than zero."
            )
        return attrs

    def _academic_year(self, label):
        from bonds.academic import get_current_academic_year, get_or_create_academic_year

        if label:
            return get_or_create_academic_year(label)
        if self.instance is not None and self.instance.academic_year_id:
            return self.instance.academic_year
        return get_current_academic_year()

    def create(self, validated_data):
        label = validated_data.pop("academic_year", None)
        year = self._academic_year(label)
        owner = validated_data.get("owner")
        if (
            owner is not None
            and LoanApplication.objects.filter(
                owner=owner, academic_year=year
            ).exists()
        ):
            raise serializers.ValidationError(
                {
                    "academic_year": (
                        "This student already has an application for "
                        f"{year.label}. A later year needs its own application."
                    )
                }
            )
        validated_data["academic_year"] = year
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # The year is fixed once the application exists, so a later edit
        # cannot move this year's fees onto another year.
        validated_data.pop("academic_year", None)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        year = instance.academic_year
        data["academic_year"] = year.label if year is not None else None
        return data


class LoanApplicationReviewSerializer(LoanApplicationSerializer):
    class Meta(LoanApplicationSerializer.Meta):
        read_only_fields = [
            "id",
            "loan_reference",
            "owner",
            "tuition_amount",
            "upkeep_amount",
            "amount",
            "created_at",
            "updated_at",
        ]


class RegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)
    # Stored on UserProfile, not User. Input-only, so it is never serialized back.
    student_registration_number = serializers.CharField(
        max_length=50,
        required=True,
        write_only=True,
    )
    # Student details live on StudentDetail, not User, so they are input-only too.
    full_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, write_only=True
    )
    programme = serializers.CharField(
        max_length=150, required=False, allow_blank=True, write_only=True
    )
    year_of_study = serializers.IntegerField(
        min_value=1, max_value=8, required=False, allow_null=True, write_only=True
    )
    phone_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        write_only=True,
        validators=[phone_validator],
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "student_registration_number",
            "full_name",
            "programme",
            "year_of_study",
            "phone_number",
            "password",
            "password_confirmation",
        ]
        read_only_fields = ["id"]

    DETAIL_FIELDS = ("full_name", "programme", "year_of_study", "phone_number")

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_student_registration_number(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Student registration number is required.")
        if UserProfile.objects.filter(student_registration_number__iexact=value).exists():
            raise serializers.ValidationError(
                "This student registration number is already registered."
            )
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirmation"]:
            raise serializers.ValidationError(
                {"password_confirmation": "Passwords do not match."}
            )

        candidate = User(username=attrs.get("username", ""), email=attrs.get("email", ""))
        try:
            password_validation.validate_password(attrs["password"], user=candidate)
        except ValidationError as error:
            raise serializers.ValidationError({"password": list(error.messages)}) from error

        attrs.pop("password_confirmation")
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        registration_number = validated_data.pop("student_registration_number")
        details = {
            key: validated_data.pop(key)
            for key in self.DETAIL_FIELDS
            if key in validated_data
        }
        if "full_name" in details:
            details["full_name"] = details["full_name"].strip()
        try:
            with transaction.atomic():  # user + profile succeed or fail together
                user = User.objects.create_user(password=password, **validated_data)
                UserProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "role": UserProfile.Role.STUDENT,
                        "student_registration_number": registration_number,
                    },
                )
                # Every student gets a details record, even if left empty for now.
                StudentDetail.objects.update_or_create(user=user, defaults=details)
        except IntegrityError:
            raise serializers.ValidationError(
                "Username, email or registration number is already in use."
            )
        return user


class StudentDetailSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    registration_number = serializers.CharField(
        source="user.profile.student_registration_number",
        read_only=True,
        allow_null=True,
        help_text="Taken from the registration; cannot be changed here.",
    )
    is_complete = serializers.BooleanField(
        read_only=True,
        help_text="True when the name, programme and year of study are all filled in.",
    )

    class Meta:
        model = StudentDetail
        fields = [
            "id",
            "username",
            "email",
            "registration_number",
            "full_name",
            "programme",
            "year_of_study",
            "phone_number",
            "is_complete",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]
        extra_kwargs = {
            "full_name": {"help_text": "Full name exactly as it should appear on the agreement."},
            "programme": {"help_text": "Programme of study, e.g. BSc Computer Science."},
            "year_of_study": {"help_text": "Current year of study, from 1 to 8."},
            "phone_number": {"help_text": "Contact phone number, e.g. +265 999 123 456."},
        }

    def validate_full_name(self, value):
        return value.strip()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["password_confirmation"]:
            raise serializers.ValidationError(
                {"password_confirmation": "Passwords do not match."}
            )

        # One generic error for every failure, so attackers learn nothing.
        generic = serializers.ValidationError({"otp": "Invalid or expired OTP."})
        email = attrs["email"].strip()

        user = (
            User.objects.filter(email__iexact=email, is_active=True)
            .order_by("id")
            .first()
        )
        record = (
            PasswordResetOTP.objects
            .filter(email__iexact=email, created_at__gte=timezone.now() - OTP_TTL)
            .order_by("-created_at")
            .first()
        )
        if not user or not record or record.attempts >= MAX_OTP_ATTEMPTS:
            raise generic

        # Encode to bytes: compare_digest raises TypeError on non-ASCII str input.
        if not secrets.compare_digest(record.otp.encode(), attrs["otp"].encode()):
            PasswordResetOTP.objects.filter(pk=record.pk).update(attempts=F("attempts") + 1)
            raise generic

        try:
            password_validation.validate_password(attrs["new_password"], user=user)
        except ValidationError as error:
            raise serializers.ValidationError(
                {"new_password": list(error.messages)}
            ) from error

        attrs["user"] = user
        attrs["otp_record"] = record
        return attrs


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = get_user_role(user)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["role"] = get_user_role(self.user)
        return data