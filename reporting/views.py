from django.shortcuts import render


from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class ReportingPermissionMixin:
    permission_classes = [IsAuthenticated]

    def has_reporting_access(self, request):
        return request.user.groups.filter(
            name="loan_board_officer"
        ).exists()

    def unavailable_response(self, report_name):
        return Response(
            {
                "report": report_name,
                "message": "Report data integration is pending."
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


class ActiveLoansReportView(ReportingPermissionMixin, APIView):

    def get(self, request):
        if not self.has_reporting_access(request):
            return Response(
                {"error": "Reporting access denied."},
                status=status.HTTP_403_FORBIDDEN
            )

        return self.unavailable_response("active_loans")


class SignedBondsReportView(ReportingPermissionMixin, APIView):

    def get(self, request):
        if not self.has_reporting_access(request):
            return Response(
                {"error": "Reporting access denied."},
                status=status.HTTP_403_FORBIDDEN
            )

        return self.unavailable_response("signed_bonds")


class DefaultersReportView(ReportingPermissionMixin, APIView):

    def get(self, request):
        if not self.has_reporting_access(request):
            return Response(
                {"error": "Reporting access denied."},
                status=status.HTTP_403_FORBIDDEN
            )

        return self.unavailable_response("defaulters")
