from django.urls import path
from . import views

from .api_views import (
    StudentDocumentCreateAPIView,
    AdminDocumentListAPIView,
    AdminDocumentPreviewAPIView,
    DocumentVerificationAPIView,
    StudentNotificationListAPIView,
)

urlpatterns = [
    path("submit/", views.submit_document, name="submit_document"),
    path("api/my-documents/", StudentDocumentCreateAPIView.as_view(), name="student_documents_api"),
    path("api/admin/documents/", AdminDocumentListAPIView.as_view(), name="admin_documents_api"),
    path("api/admin/documents/<int:pk>/preview/", AdminDocumentPreviewAPIView.as_view(), name="admin_document_preview_api"),
    path("api/<int:pk>/verify/", DocumentVerificationAPIView.as_view(), name="document_verification_api"),
    path("api/my-notifications/", StudentNotificationListAPIView.as_view(), name="student_notifications_api"),
]