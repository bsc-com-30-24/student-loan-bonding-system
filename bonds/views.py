from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Bond
from .serializers import BondSerializer, BondStatusUpdateSerializer


class BondListCreateView(generics.ListCreateAPIView):
    serializer_class = BondSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Bond.objects.all()

        return Bond.objects.filter(student=user)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


class BondDetailView(generics.RetrieveAPIView):
    serializer_class = BondSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Bond.objects.all()

        return Bond.objects.filter(student=user)


class BondStatusUpdateView(generics.UpdateAPIView):
    serializer_class = BondStatusUpdateSerializer
    permission_classes = [IsAuthenticated]

    http_method_names = ["patch", "head", "options"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Bond.objects.all()

        return Bond.objects.none()

    def perform_update(self, serializer):
        from django.utils import timezone

        serializer.save(
            reviewed_by=self.request.user,
            reviewed_at=timezone.now(),
        )