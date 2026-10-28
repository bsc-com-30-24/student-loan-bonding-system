
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, permissions, parsers, status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Document
from .serializers import DocumentSerializer


class StudentDocumentListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [
        parsers.MultiPartParser,
        parsers.FormParser,
        parsers.JSONParser,
    ]

    def get_queryset(self):
        return Document.objects.filter(
            student=self.request.user
        ).order_by("-submitted_at")

    def perform_create(self, serializer):
        serializer.save(
            student=self.request.user,
            status="pending",
        )


class DocumentVerificationAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        new_status = request.data.get("status")
        reason = request.data.get("rejection_reason", "").strip()

        if new_status not in ("verified", "rejected"):
            return Response(
                {"error": "Status must be verified or rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status == "rejected" and not reason:
            return Response(
                {"error": "A rejection reason is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        document.status = new_status
        document.rejection_reason = (
            reason if new_status == "rejected" else ""
        )
        document.reviewed_by = request.user
        document.reviewed_at = timezone.now()

        document.save(
            update_fields=[
                "status",
                "rejection_reason",
                "reviewed_by",
                "reviewed_at",
            ]
        )

        return Response({
            "id": document.id,
            "status": document.status,
            "rejection_reason": document.rejection_reason,
            "reviewed_by": request.user.username,
            "reviewed_at": document.reviewed_at,
        })
