from django.urls import path
from .views import (
    AcademicYearListCreateView,
    BondListCreateView,
    BondHistoryView,
    BondDetailView,
    BondStatusUpdateView,
)

urlpatterns = [
    path("", BondListCreateView.as_view(), name="bond-list-create"),
    path("history/", BondHistoryView.as_view(), name="bond-history"),
    path(
        "academic-years/",
        AcademicYearListCreateView.as_view(),
        name="academic-year-list",
    ),
    path("<int:pk>/", BondDetailView.as_view(), name="bond-detail"),
    path(
        "<int:pk>/status/",
        BondStatusUpdateView.as_view(),
        name="bond-status-update",
    ),
]