import os

from django.core.exceptions import ValidationError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png")
ALLOWED_FILES_TEXT = "PDF, JPG or PNG, up to 5 MB"


def _matches_signature(extension, head):
    if extension == ".pdf":
        return b"%PDF" in head[:1024]
    if extension == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    return False


def validate_uploaded_document(uploaded_file):
    """Reject anything that is not a real PDF/JPG/PNG within the size limit.

    Uploaded files are later shown to administrators in the browser, so an
    HTML or script file renamed or uploaded as-is would be a stored-XSS risk.
    """
    name = os.path.basename(getattr(uploaded_file, "name", "") or "")
    extension = os.path.splitext(name)[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Unsupported file type. Upload a {ALLOWED_FILES_TEXT} file.")

    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise ValidationError("File is too large. The maximum size is 5 MB.")

    uploaded_file.seek(0)
    head = uploaded_file.read(1024)
    uploaded_file.seek(0)

    if not _matches_signature(extension, head):
        raise ValidationError("The file content does not match its file type.")