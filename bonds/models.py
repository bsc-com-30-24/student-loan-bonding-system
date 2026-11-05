from django.conf import settings
from django.db import models, transaction
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


    def save(self, *args, **kwargs):
        actor = getattr(self, "_history_actor", None)
        reason = getattr(self, "_history_reason", "")

        try:
            with transaction.atomic():
                previous_status = None

                # Find the bond's current database status.
                if self.pk is not None:
                    previous_status = (
                        Bond.objects.select_for_update()
                        .filter(pk=self.pk)
                        .values_list("status", flat=True)
                        .first()
                    )

                # Check whether this save includes the status field.
                update_fields = kwargs.get("update_fields")
                status_saved = (
                    update_fields is None
                    or "status" in update_fields
                )

                # Save the bond normally.
                super().save(*args, **kwargs)

                # Record an actual status change.
                if (
                    previous_status is not None
                    and status_saved
                    and previous_status != self.status
                ):
                    BondStatusHistory.objects.create(
                        bond=self,
                        previous_status=previous_status,
                        new_status=self.status,
                        changed_by=actor,
                        reason=reason or (
                            self.rejection_reason
                            if self.status == "rejected"
                            else ""
                        ),
                    )
        finally:
            self.__dict__.pop("_history_actor", None)
            self.__dict__.pop("_history_reason", None)


    
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
