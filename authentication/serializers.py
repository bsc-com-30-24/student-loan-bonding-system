from rest_framework import serializers
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import LoanApplication, UserProfile, get_user_role

User = get_user_model()


class LoanApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanApplication
        fields = [
            "id",
            "owner",
            "amount",
            "purpose",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "status", "created_at", "updated_at"]

    def validate_amount(self, amount):
        if amount <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return amount


class LoanApplicationSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()

    class Meta:
        model = LoanApplication
        fields = [
            "id",
            "owner",
            "tuition_amount",
            "upkeep_amount",
            "amount",  # Calculated safely for the API
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "amount", "status", "created_at", "updated_at"]

    def get_amount(self, obj):
        return obj.get_total_amount()

    def validate(self, attrs):
        tuition = attrs.get("tuition_amount", 0)
        upkeep = attrs.get("upkeep_amount", 0)
        if tuition + upkeep <= 0:
            raise serializers.ValidationError("The combined loan amount must be greater than zero.")
        return attrs

class LoanApplicationReviewSerializer(LoanApplicationSerializer):
    class Meta(LoanApplicationSerializer.Meta):
        read_only_fields = [
            "id",
            "owner",
            "tuition_amount",
            "upkeep_amount",
            "created_at",
            "updated_at",
        ]

class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "password_confirmation"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirmation"):
            raise serializers.ValidationError({"password_confirmation": "Passwords do not match."})
        try:
            password_validation.validate_password(attrs["password"], user=User(**attrs))
        except ValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        UserProfile.objects.create(user=user, role=UserProfile.Role.STUDENT)
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["password_confirmation"]:
            raise serializers.ValidationError(
                {"password_confirmation": "Passwords do not match."}
            )

        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User._default_manager.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist) as error:
            raise serializers.ValidationError(
                {"token": "Invalid or expired password reset token."}
            ) from error

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError(
                {"token": "Invalid or expired password reset token."}
            )

        try:
            password_validation.validate_password(attrs["new_password"], user=user)
        except ValidationError as error:
            raise serializers.ValidationError({"new_password": error.messages}) from error

        attrs["user"] = user
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
    