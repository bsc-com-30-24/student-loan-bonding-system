
from django.urls import path

from .views import (
    ActiveLoansReportView,
    BondReportView,
    DefaultersReportView,
    SignedBondsReportView,
)

urlpatterns = [
    path("", BondReportView.as_view(), name="bond-report"),
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
