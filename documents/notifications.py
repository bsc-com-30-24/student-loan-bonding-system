from django.conf import settings
from django.core.mail import send_mail

from .models import Notification


def notify_document_rejected(document):
    """Tell the student their document was rejected (in-app notification + email).

    Used by both the Django admin and the verification API so that a
    rejection always produces the same notification, whichever way it is made.
    """
    message = (
        f"Your {document.get_document_type_display()} "
        f"document has been rejected. "
        f"Reason: {document.rejection_reason}. "
        "Please correct the issue and submit the document again."
    )

    Notification.objects.create(
        student=document.student,
        document=document,
        message=message,
    )

    if document.student.email:
        send_mail(
            subject="Your document has been rejected",
            message=(
                f"Hello {document.student.username},\n\n"
                f"{message}\n\n"
                "Student Loan Bonding System"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[document.student.email],
            fail_silently=True,
        )