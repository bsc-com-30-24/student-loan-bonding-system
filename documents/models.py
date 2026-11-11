from django.conf import settings
from django.db import models


class Document(models.Model):

    DOCUMENT_TYPES = [
        ("student_id", "Student ID"),
        ("affidavit", "Affidavit Form"),
        ("guarantor_form", "Guarantor Form"),
        ("other_letter", "Other Letter"),
        ("national_id", "National ID"),
        ("guarantor_id", "Guarantor ID"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    loan_application = models.ForeignKey(
        "authentication.LoanApplication",
        on_delete=models.SET_NULL,
        related_name="documents",
        null=True,
        blank=True,
    )

    document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPES,
    )

    file = models.FileField(upload_to="student_documents/")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    rejection_reason = models.TextField(blank=True, default="")

    submitted_at = models.DateTimeField(auto_now_add=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_documents",
    )

    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return (
            f"{self.get_document_type_display()} - "
            f"{self.student} ({self.status})"
        )


class Notification(models.Model):

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_notifications",
    )

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.student.username}"