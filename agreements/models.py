import uuid

from django.db import models


class Agreement(models.Model):

    class Status(models.TextChoices):
        GENERATED = 'GENERATED', 'Generated'
        PENDING_SIGNATURE = 'PENDING_SIGNATURE', 'Pending Signature'
        SIGNED = 'SIGNED', 'Signed'
        COUNTERSIGNED = 'COUNTERSIGNED', 'Countersigned'

    agreement_number = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    student_id = models.CharField(max_length=50)

    loan_reference = models.CharField(max_length=100)

    agreement_content = models.TextField()

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.GENERATED
    )

    generated_at = models.DateTimeField(auto_now_add=True)

    student_signed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    board_countersigned_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.agreement_number)