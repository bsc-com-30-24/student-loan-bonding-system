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