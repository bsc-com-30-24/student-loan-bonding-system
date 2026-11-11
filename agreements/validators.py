import os

from django.core.exceptions import ValidationError

MAX_SIGNED_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_signed_pdf(uploaded_file):
    """A signed agreement must be a real, non-empty PDF up to 10 MB."""
    extension = os.path.splitext(uploaded_file.name)[1].lower()

    if extension != ".pdf":
        raise ValidationError("Upload the signed agreement as a PDF file.")

    if uploaded_file.size == 0:
        raise ValidationError("The uploaded file is empty.")

    if uploaded_file.size > MAX_SIGNED_UPLOAD_SIZE:
        raise ValidationError("File is too large. The maximum size is 10 MB.")

    header = uploaded_file.read(5)
    uploaded_file.seek(0)

    if header != b"%PDF-":
        raise ValidationError("The uploaded file is not a valid PDF.")