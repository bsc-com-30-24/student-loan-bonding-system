from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.access import is_university_admin
from authentication.models import UserProfile, get_user_role
from bonds.models import Bond
from bonds.serializers import BondHistorySerializer

User = get_user_model()


class StudentBondVerificationView(APIView):
    """Employers and university administrators look up a student's bonds."""

    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        role = get_user_role(request.user)
        in_group = request.user.groups.filter(
            name__in=["university_admin", "employer"]
        ).exists()
        allowed = role in (
            UserProfile.Role.UNIVERSITY_ADMIN,
            UserProfile.Role.EMPLOYER,
        ) or in_group or is_university_admin(request.user)

        if not allowed:
            return Response(
                {"error": "You are not authorized to verify bonds."},
                status=403,
            )

        student = get_object_or_404(User, pk=student_id)
        bonds = (
            Bond.objects.filter(student=student)
            .select_related(
                "student",
                "student__profile",
                "student__student_detail",
                "academic_year",
                "loan_application",
                "agreement",
            )
            .order_by("-academic_year__label", "-created_at")
        )
        profile = getattr(student, "profile", None)
        detail = getattr(student, "student_detail", None)
        return Response(
            {
                "student_id": student.id,
                "username": student.username,
                "registration_number": getattr(
                    profile, "student_registration_number", None
                ),
                "full_name": detail.full_name if detail is not None else "",
                "programme": detail.programme if detail is not None else "",
                "bonds": BondHistorySerializer(bonds, many=True).data,
            }
        )
