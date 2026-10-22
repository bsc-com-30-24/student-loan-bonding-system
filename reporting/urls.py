
from django.urls import path

from .views import (
    ActiveLoansReportView,
    SignedBondsReportView,
    DefaultersReportView,
)

urlpatterns = [
    path(
        "active-loans/",
        ActiveLoansReportView.as_view(),
        name="active-loans-report"
    ),
    path(
        "signed-bonds/",
        SignedBondsReportView.as_view(),
        name="signed-bonds-report"
    ),
    path(
        "defaulters/",
        DefaultersReportView.as_view(),
        name="defaulters-report"
    ),
]
