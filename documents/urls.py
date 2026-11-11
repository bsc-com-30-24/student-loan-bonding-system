from django.urls import path

from . import views
from .api_views import (
    AdminDocumentListAPIView,
    AdminDocumentPreviewAPIView,
    DocumentDownloadAPIView,
    DocumentVerificationAPIView,
    StudentDocumentCreateAPIView,
    StudentNotificationListAPIView,
    StudentNotificationMarkReadAPIView,
)

urlpatterns = [
    # Web form (not part of the API schema)
    path("documents/submit/", views.submit_document, name="submit_document"),

    # Student API
    path(
        "api/my-documents/",
        StudentDocumentCreateAPIView.as_view(),
        name="student_documents_api",
    ),
    path(
        "api/my-notifications/",
        StudentNotificationListAPIView.as_view(),
        name="student_notifications_api",
    ),
    path(
        "api/my-notifications/<int:pk>/read/",
        StudentNotificationMarkReadAPIView.as_view(),
        name="student_notification_read_api",
    ),

    # Download: students get their own files, administrators get any file
    path(
        "api/<int:pk>/download/",
        DocumentDownloadAPIView.as_view(),
        name="document_download_api",
    ),

    # Administrator API
    path(
        "api/admin/documents/",
        AdminDocumentListAPIView.as_view(),
        name="admin_documents_api",
    ),
    path(
        "api/admin/documents/<int:pk>/preview/",
        AdminDocumentPreviewAPIView.as_view(),
        name="admin_document_preview_api",
    ),
    path(
        "api/admin/documents/<int:pk>/verify/",
        DocumentVerificationAPIView.as_view(),
        name="document_verification_api",
    ),
]