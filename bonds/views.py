from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from django.utils import timezone
from .models import Bond
from .serializers import (
    BondSerializer,
    BondStatusUpdateSerializer,
    BondStatusHistorySerializer,
)

from django.shortcuts import get_object_or_404


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
        bond = serializer.instance

        bond._history_actor = self.request.user
        bond._history_reason = serializer.validated_data.get(
            "rejection_reason", ""
        )

        serializer.save(
            reviewed_by=self.request.user,
            reviewed_at=timezone.now(),
        )



class BondStatusHistoryView(generics.ListAPIView):
    serializer_class = BondStatusHistorySerializer
    permission_classes = [IsAuthenticated]

    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            bonds = Bond.objects.all()
        else:
            bonds = Bond.objects.filter(student=user)

        bond = get_object_or_404(
            bonds,
            pk=self.kwargs["pk"],
        )

        return bond.status_history.select_related(
            "changed_by"
        )
