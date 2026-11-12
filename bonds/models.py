import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q


class AcademicYear(models.Model):
    """One bonding cycle, for example 2026 or 2025/2026.

    A bond belongs to exactly one academic year. Later years get their own
    bond and their own amount; they never replace an earlier year.
    """

    label = models.CharField(max_length=20, unique=True)
    is_current = models.BooleanField(
        default=False,
        help_text="The year new applications go into. Only one year is current.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-label"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_current"],
                condition=Q(is_current=True),
                name="only_one_current_academic_year",
            ),
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_current:
                AcademicYear.objects.exclude(pk=self.pk).filter(
                    is_current=True
                ).update(is_current=False)
            super().save(*args, **kwargs)

    def __str__(self):
        return self.label


class Bond(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
    ]

    bond_reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bonds",
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="bonds",
        null=True,
        blank=True,
    )

    loan_application = models.ForeignKey(
        "authentication.LoanApplication",
        on_delete=models.PROTECT,
        related_name="bonds",
        null=True,
        blank=True,
    )

    # Snapshots taken when the bond is created. Later applications and
    # profile edits must not change a year that was already recorded.
    registration_number = models.CharField(max_length=50, blank=True, default="")

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

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    documents = models.ManyToManyField(
        "documents.Document",
        related_name="bonds",
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    rejection_reason = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_bonds",
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                name="unique_bond_per_student_per_academic_year",
            )
        ]

    def __str__(self):
        year = self.academic_year.label if self.academic_year_id else "no year"
        return f"Bond {self.bond_reference} ({year}) - {self.status}"