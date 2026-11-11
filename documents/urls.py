
from django.urls import path
from . import views
from .api_views import (
    StudentDocumentListCreateAPIView,
    DocumentVerificationAPIView,
)

urlpatterns = [
    
    path(
        "submit/",
        views.submit_document,
        name="submit_document",
    ),

    
    path(
        "api/my-documents/",
        StudentDocumentListCreateAPIView.as_view(),
        name="student_documents_api",
    ),

    
    path(
        "api/<int:pk>/verify/",
        DocumentVerificationAPIView.as_view(),
        name="document_verification_api",
    ),
]
