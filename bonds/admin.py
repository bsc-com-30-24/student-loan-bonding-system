from django.contrib import admin
from .models import AcademicYear, Bond


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("label", "is_current", "created_at")
    list_filter = ("is_current",)
    search_fields = ("label",)


@admin.register(Bond)
class BondAdmin(admin.ModelAdmin):
    list_display = (
        "bond_reference",
        "student",
        "academic_year",
        "registration_number",
        "amount",
        "status",
        "created_at",
    )

    list_filter = ("status", "academic_year", "created_at")

    search_fields = (
        "student__username",
        "student__email",
        "registration_number",
        "bond_reference",
    )

    readonly_fields = (
        "bond_reference",
        "created_at",
        "updated_at",
    )