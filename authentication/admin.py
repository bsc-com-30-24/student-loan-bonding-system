from django.contrib import admin

from .models import LoanApplication, UserProfile

from django.contrib import admin
from .models import LoanApplication

@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "owner",
        "tuition_amount",
        "upkeep_amount",
        "get_total_amount",  # <-- Replaces "amount"
        "status",
        "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["owner__username", "owner__email"]

    # Optional: rename the column header in the admin panel
    @admin.display(description="Total Amount")
    def get_total_amount(self, obj):
        return obj.get_total_amount()
