from django.db.models import ProtectedError
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from authentication.access import IsUniversityAdminOrReadOnly

from .models import AcademicYear
from .serializers import AcademicYearSerializer

TAG = "Academic Years"


@extend_schema_view(
    list=extend_schema(
        tags=[TAG],
        summary="List academic years",
        description=(
            "Returns every academic year, newest first. Any logged-in user can "
            "read them. Bonds, agreements and documents are all filed under one."
        ),
    ),
    retrieve=extend_schema(
        tags=[TAG],
        summary="Get one academic year",
        description="Returns a single academic year.",
    ),
    create=extend_schema(
        tags=[TAG],
        summary="Create an academic year",
        description=(
            "University administrators only. The label must be unique "
            '(for example "2026"). Set is_current to true to make it the year '
            "new applications go into; the previous current year is retired."
        ),
    ),
    update=extend_schema(
        tags=[TAG],
        summary="Update an academic year",
        description="University administrators only.",
    ),
    partial_update=extend_schema(
        tags=[TAG],
        summary="Partially update an academic year",
        description=(
            "University administrators only. Send only the fields to change, "
            'for example {"is_current": true} to switch the current year.'
        ),
    ),
    destroy=extend_schema(
        tags=[TAG],
        summary="Delete an academic year",
        description=(
            "University administrators only. A year that already has documents, "
            "bonds or agreements cannot be deleted, so the history is never lost."
        ),
    ),
)
class AcademicYearViewSet(viewsets.ModelViewSet):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    permission_classes = [IsUniversityAdminOrReadOnly]

    @extend_schema(
        tags=[TAG],
        summary="Get the current academic year",
        description=(
            "Returns the year that new applications and documents are filed "
            "under. Returns 404 if no year has been made current yet."
        ),
        responses={
            200: AcademicYearSerializer,
            404: OpenApiResponse(description="No academic year is current."),
        },
    )
    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        year = AcademicYear.get_current()
        if year is None:
            raise NotFound("No academic year is current yet.")
        return Response(self.get_serializer(year).data)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise serializers.ValidationError(
                "This academic year already has records (documents, bonds or "
                "agreements) and cannot be deleted."
            )