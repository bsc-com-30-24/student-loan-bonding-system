from django.contrib import admin
from django.db import transaction
from django.utils import timezone

from .models import Bond, BondStatusHistory

@admin.register(Bond)
class BondAdmin(admin.ModelAdmin):
    list_display = (
        "bond_reference",
        "student",
        "status",
        "created_at",
        "updated_at",
    )

    list_filter = ("status", "created_at")

    search_fields = (
        "student__username",
        "student__email",
        "bond_reference",
    )

    readonly_fields = (
        "bond_reference",
        "created_at",
        "updated_at",
    )


    @transaction.atomic
    def save_model(self, request, obj, form, change):
        previous_status = None

        # Find the status currently stored in the database.
        if change:
            previous_status = (
                Bond.objects.select_for_update()
                .filter(pk=obj.pk)
                .values_list("status", flat=True)
                .first()
            )

        status_changed = (
            change
            and previous_status is not None
            and previous_status != obj.status
        )

        # Record the administrator responsible for a change.
        if status_changed:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()

        # Save the updated bond.
        super().save_model(request, obj, form, change)

        # Create a history entry only when the status changed.
        if status_changed:
            BondStatusHistory.objects.create(
                bond=obj,
                previous_status=previous_status,
                new_status=obj.status,
                changed_by=request.user,
                reason=(
                    obj.rejection_reason
                    if obj.status == "rejected"
                    else ""
                ),
            )
