from django.contrib import admin
from .models import Bond

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
    
    
    def save_model(self, request, obj, form, change):
        if change:
            obj._history_actor = request.user

            obj._history_reason = (
                obj.rejection_reason
                if obj.status == "rejected"
                else ""
            )

        super().save_model(request, obj, form, change)
