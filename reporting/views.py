from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.access import is_loan_board_officer, is_university_admin
from agreements.models import Agreement
from bonds.serializers import BondHistorySerializer
from bonds.views import bonds_for_user


def can_view_reports(user):
    return is_university_admin(user) or is_loan_board_officer(user)


class ReportingPermissionMixin:
    permission_classes = [IsAuthenticated]

    def denied(self):
        return Response({"error": "Reporting access denied."}, status=403)


class BondReportView(ReportingPermissionMixin, APIView):
    """Account, student details and amounts, one row per bond and year."""

    def get(self, request):
        if not can_view_reports(request.user):
            return self.denied()

        bonds = bonds_for_user(request.user)
        label = (request.query_params.get("academic_year") or "").strip()
        if label:
            bonds = bonds.filter(academic_year__label=label)
        status_filter = (request.query_params.get("status") or "").strip()
        if status_filter:
            bonds = bonds.filter(status=status_filter)

        rows = BondHistorySerializer(bonds, many=True).data
        return Response(
            {
                "report": "bonds",
                "academic_year": label or None,
                "count": len(rows),
                "results": rows,
            }
        )


class ActiveLoansReportView(ReportingPermissionMixin, APIView):

    def get(self, request):
        if not can_view_reports(request.user):
            return self.denied()

        bonds = bonds_for_user(request.user).filter(
            status__in=["pending", "approved"]
        )
        rows = BondHistorySerializer(bonds, many=True).data
        return Response(
            {"report": "active_loans", "count": len(rows), "results": rows}
        )


class SignedBondsReportView(ReportingPermissionMixin, APIView):

    def get(self, request):
        if not can_view_reports(request.user):
            return self.denied()

        bonds = bonds_for_user(request.user).filter(
            agreement__status__in=[
                Agreement.Status.SIGNED,
                Agreement.Status.COUNTERSIGNED,
            ]
        )
        rows = BondHistorySerializer(bonds, many=True).data
        return Response(
            {"report": "signed_bonds", "count": len(rows), "results": rows}
        )


class DefaultersReportView(ReportingPermissionMixin, APIView):

    def get(self, request):
        if not can_view_reports(request.user):
            return self.denied()

        bonds = bonds_for_user(request.user).filter(status="rejected")
        rows = BondHistorySerializer(bonds, many=True).data
        return Response(
            {"report": "defaulters", "count": len(rows), "results": rows}
        )
