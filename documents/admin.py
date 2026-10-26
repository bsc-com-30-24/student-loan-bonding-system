
from django import forms
from django.contrib import admin
from django.utils import timezone

from .models import Document


class DocumentVerificationForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ("status", "rejection_reason")

    def clean(self):
        cleaned_data = super().clean()

        status_value = cleaned_data.get("status")
        reason = cleaned_data.get("rejection_reason", "").strip()

        if status_value == "rejected" and not reason:
            self.add_error(
                "rejection_reason",
                "Please provide a reason for rejecting this document.",
            )

        return cleaned_data


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    form = DocumentVerificationForm

    list_display = (
        "id",
        "student",
        "document_type",
        "status",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
    )

    list_filter = ("status", "document_type")
    search_fields = ("student__username",)
    ordering = ("-submitted_at",)

    readonly_fields = (
        "student",
        "document_type",
        "file",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
    )

    fields = (
        "student",
        "document_type",
        "file",
        "submitted_at",
        "status",
        "rejection_reason",
        "reviewed_by",
        "reviewed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data:
            if obj.status in ("verified", "rejected"):
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()

            if obj.status == "verified":
                obj.rejection_reason = ""

        super().save_model(request, obj, form, change)
