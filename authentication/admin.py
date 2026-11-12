from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    LoanApplication,
    PasswordResetOTP,
    StudentDetail,
    UserProfile,
    get_user_role,
)

User = get_user_model()


class UserProfileInline(admin.StackedInline):
    """Lets an admin set a user's role and registration number on the user page.

    This is how non-student roles (admin, loan board officer, employer) are assigned.
    """

    model = UserProfile
    fk_name = "user"
    can_delete = False
    verbose_name_plural = "Profile (role and registration number)"


class StudentDetailInline(admin.StackedInline):
    """The student's name, programme, year of study and phone number."""

    model = StudentDetail
    fk_name = "user"
    can_delete = False
    verbose_name_plural = "Student details"


try:
    admin.site.unregister(User)
except NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline, StudentDetailInline]
    list_display = BaseUserAdmin.list_display + ("get_role",)
    list_select_related = ("profile",)

    @admin.display(description="Role")
    def get_role(self, obj):
        return get_user_role(obj)


@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "loan_reference",
        "owner",
        "academic_year",
        "tuition_amount",
        "upkeep_amount",
        "total_amount",
        "status",
        "created_at",
    ]
    list_filter = ["status", "academic_year", "created_at"]
    search_fields = ["loan_reference", "owner__username", "owner__email"]
    readonly_fields = ["loan_reference", "created_at", "updated_at"]

    @admin.display(description="Total Amount")
    def total_amount(self, obj):
        return obj.get_total_amount()


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    # The OTP value itself is deliberately never shown.
    list_display = ["email", "attempts", "created_at"]
    fields = ["email", "attempts", "created_at"]
    readonly_fields = ["email", "attempts", "created_at"]

    def has_add_permission(self, request):
        return False