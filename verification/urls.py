
from django.urls import path
from .views import StudentBondVerificationView

urlpatterns = [
    path(
        "bonds/<int:student_id>/",
        StudentBondVerificationView.as_view(),
        name="student-bond-verification"
    ),
]
