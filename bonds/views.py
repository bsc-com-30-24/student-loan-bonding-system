from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Bond
from .serializers import BondSerializer, BondStatusUpdateSerializer


@extend_schema(
    tags=["Bond Management"],
    summary="List or create bonds",
    description=(
        "GET: Returns bond records belonging to the authenticated student. "
        "Staff users can view all bonds. "
        "POST: Creates a new bond and automatically assigns it to the "
        "authenticated user. The student field is assigned by the system."
    ),
)
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


@extend_schema(
    tags=["Bond Management"],
    summary="Retrieve a bond",
    description=(
        "Returns the details of a specific bond identified by its ID. "
        "Students can access their own bonds, while staff users can access "
        "all bonds. Returns 404 if the bond does not exist or is not "
        "accessible to the authenticated user."
    ),
)
class BondDetailView(generics.RetrieveAPIView):
    serializer_class = BondSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Bond.objects.all()

        return Bond.objects.filter(student=user)


@extend_schema(
    tags=["Bond Management"],
    summary="Update a bond's status",
    description=(
        "Allows authenticated staff users to partially update a bond using "
        "its ID. Send a PATCH request containing the fields accepted by "
        "BondStatusUpdateSerializer. The system automatically records the "
        "reviewing staff member and review date/time. Non-staff users cannot "
        "access bonds through this endpoint."
    ),
)
class BondStatusUpdateView(generics.UpdateAPIView):
    serializer_class = BondStatusUpdateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch", "head", "options"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Bond.objects.all()

        return Bond.objects.none()

    def perform_update(self, serializer):
        serializer.save(
            reviewed_by=self.request.user,
            reviewed_at=timezone.now(),
        )
