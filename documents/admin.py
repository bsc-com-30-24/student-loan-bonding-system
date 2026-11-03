
import mimetypes

from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Document, Notification


class DocumentVerificationForm(forms.ModelForm):

    class Meta:
        model = Document
        fields = ("status", "rejection_reason")

    def clean(self):
        cleaned_data = super().clean()

        status_value = cleaned_data.get("status")
        reason = (cleaned_data.get("rejection_reason") or "").strip()

        if status_value == "rejected" and not reason:
            self.add_error(
                "rejection_reason",
                "Please provide a reason for rejecting this document."
            )

        return cleaned_data


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):

    form = DocumentVerificationForm

    list_display = (
        "id",
        "student",
        "document_type",
        "view_document",
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
        "view_document",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
    )

    fields = (
        "student",
        "document_type",
        "file",
        "view_document",
        "submitted_at",
        "status",
        "rejection_reason",
        "reviewed_by",
        "reviewed_at",
    )

    @admin.display(description="Uploaded Document")
    def view_document(self, obj):

        if not obj or not obj.file:
            return "No document uploaded"

        preview_url = reverse(
            "admin_document_preview_api",
            kwargs={"pk": obj.pk}
        )

        content_type, _ = mimetypes.guess_type(
            obj.file.name
        )

        document_type = obj.get_document_type_display()

        if content_type and content_type.startswith("image/"):
            return format_html(
                '<div><strong>{}</strong><br>'
                '<a href="{}" target="_blank" rel="noopener">'
                '<img src="{}" style="max-width:180px; '
                'max-height:140px; object-fit:contain;" />'
                '</a></div>',
                document_type,
                preview_url,
                preview_url,
            )

        return format_html(
            '<strong>{}</strong><br>'
            '<a href="{}" target="_blank" rel="noopener">'
            'Open Uploaded Document</a>',
            document_type,
            preview_url,
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):

        old_status = None

        if change:
            old_status = Document.objects.get(
                pk=obj.pk
            ).status

        if change and "status" in form.changed_data:

            if obj.status in ("verified", "rejected"):
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()

            if obj.status == "verified":
                obj.rejection_reason = ""

        super().save_model(request, obj, form, change)

        if (
            change
            and obj.status == "rejected"
            and old_status != "rejected"
        ):

            message = (
                f"Your {obj.get_document_type_display()} "
                f"document has been rejected. "
                f"Reason: {obj.rejection_reason}. "
                "Please correct the issue and submit the document again."
            )

            Notification.objects.create(
                student=obj.student,
                document=obj,
                message=message,
            )

            if obj.student.email:
                send_mail(
                    subject="Your document has been rejected",
                    message=(
                        f"Hello {obj.student.username},\n\n"
                        f"{message}\n\n"
                        "Student Loan Bonding System"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[obj.student.email],
                    fail_silently=True,
                )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "student",
        "document",
        "is_read",
        "created_at",
    )

    list_filter = ("is_read", "created_at")
    search_fields = ("student__username", "message")
    ordering = ("-created_at",)

    readonly_fields = (
        "student",
        "document",
        "message",
        "created_at",
    )

    fields = (
        "student",
        "document",
        "message",
        "is_read",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
