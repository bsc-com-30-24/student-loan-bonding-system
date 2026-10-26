
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class StudentBondVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        # Only university admins and employers can verify bonds.
        allowed_roles = ["university_admin", "employer"]

        is_allowed = request.user.groups.filter(
            name__in=allowed_roles
        ).exists()

        if not is_allowed:
            return Response(
                {"error": "You are not authorized to verify bonds."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Bond records will be connected later.
        return Response(
            {
                "message": "Bond verification is not yet connected.",
                "student_id": student_id
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

