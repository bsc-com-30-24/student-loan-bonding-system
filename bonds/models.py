from django.conf import settings
from django.db import models
import uuid


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

    def __str__(self):
        return f"Bond {self.bond_reference} - {self.status}"

    
class BondStatusHistory(models.Model):
    bond = models.ForeignKey(
        Bond,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    previous_status = models.CharField(
        max_length=20,
        choices=Bond.STATUS_CHOICES,
    )

    new_status = models.CharField(
        max_length=20,
        choices=Bond.STATUS_CHOICES,
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bond_status_changes",
    )

    changed_at = models.DateTimeField(
        auto_now_add=True,
    )

    reason = models.TextField(
        blank=True,
        default="",
    )

    class Meta:
        ordering = ["-changed_at", "-id"]

    def __str__(self):
        return (
            f"Bond {self.bond_id}: "
            f"{self.previous_status} -> {self.new_status}"
        )
