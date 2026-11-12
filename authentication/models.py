from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.utils import timezone


def get_user_role(user):
    # Anonymous requests happen when drf-spectacular builds the Swagger schema,
    # and when unauthenticated clients hit the API. They have no profile.
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if user.is_superuser:
        return "university_admin"
    try:
        return user.profile.role
    except UserProfile.DoesNotExist:
        return UserProfile.Role.STUDENT


class UserProfile(models.Model):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        UNIVERSITY_ADMIN = "university_admin", "University Admin"
        LOAN_BOARD_OFFICER = "loan_board_officer", "Loan Board Officer"
        EMPLOYER = "employer", "Employer"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    student_registration_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.user.username} ({self.role})"


phone_validator = RegexValidator(
    r"^\+?[0-9 ()-]{7,20}$",
    "Enter a valid phone number, for example +265 999 123 456.",
)


class StudentDetail(models.Model):
    """The student's personal details, kept once and reused on every agreement.

    The registration number stays on UserProfile; this holds the rest.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_detail",
    )
    full_name = models.CharField(max_length=150, blank=True, default="")
    programme = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="Programme of study, for example BSc Computer Science.",
    )
    year_of_study = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(8)],
    )
    phone_number = models.CharField(
        max_length=20, blank=True, default="", validators=[phone_validator]
    )
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_complete(self):
        """True when everything an agreement needs about the student is filled in."""
        return bool(self.full_name and self.programme and self.year_of_study)

    def __str__(self):
        return f"{self.full_name or self.user.username} (details)"


class LoanApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loan_applications",
    )
    loan_reference = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
    )
    tuition_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    upkeep_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    academic_year = models.ForeignKey(
        "bonds.AcademicYear",
        on_delete=models.PROTECT,
        related_name="loan_applications",
        null=True,
        blank=True,
        help_text="The year these tuition and upkeep amounts belong to.",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "academic_year"],
                name="one_loan_application_per_student_per_academic_year",
            ),
        ]

    def get_total_amount(self):
        return self.tuition_amount + self.upkeep_amount

    def save(self, *args, **kwargs):
        # First save gets a database ID; then the reference is built from it,
        # e.g. ID 15 in 2026 -> SLBS-2026-00015. Both saves succeed or neither does.
        if self.academic_year_id is None:
            from bonds.academic import get_current_academic_year

            self.academic_year = get_current_academic_year()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = list(update_fields) + ["academic_year"]
        with transaction.atomic():
            super().save(*args, **kwargs)
            if not self.loan_reference:
                self.loan_reference = f"SLBS-{timezone.now().year}-{self.pk:05d}"
                super().save(update_fields=["loan_reference"])

    def __str__(self):
        return f"Loan application {self.pk} (Total: {self.get_total_amount()})"


class PasswordResetOTP(models.Model):
    email = models.EmailField(db_index=True)
    otp = models.CharField(max_length=6)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email