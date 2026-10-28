
from django.urls import path
from . import views
from .api_views import (
    StudentDocumentListCreateAPIView,
    DocumentVerificationAPIView,
)

urlpatterns = [
    # Existing document submission page
    path(
        "submit/",
        views.submit_document,
        name="submit_document",
    ),

    # API for students to submit and view their own documents
    path(
        "api/my-documents/",
        StudentDocumentListCreateAPIView.as_view(),
        name="student_documents_api",
    ),

    # API for staff to verify or reject submitted documents
    path(
        "api/<int:pk>/verify/",
        DocumentVerificationAPIView.as_view(),
        name="document_verification_api",
    ),
]
