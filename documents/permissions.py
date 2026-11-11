from rest_framework.permissions import BasePermission

from authentication.models import UserProfile, get_user_role

# Roles allowed to review (verify / reject / preview / download any) student documents.
# Django staff users are always allowed too, so the Django admin preview keeps working.
# To let loan board officers review documents as well, add
# UserProfile.Role.LOAN_BOARD_OFFICER to this set.
REVIEWER_ROLES = frozenset({UserProfile.Role.UNIVERSITY_ADMIN})


def is_student(user):
    """A logged-in student (staff accounts and other roles are not students)."""
    return bool(
        user
        and user.is_authenticated
        and not user.is_staff
        and get_user_role(user) == UserProfile.Role.STUDENT
    )


def is_document_reviewer(user):
    """A university administrator (or Django staff)."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or get_user_role(user) in REVIEWER_ROLES)
    )


class IsStudent(BasePermission):
    """Logged-in students only (staff accounts and other roles are refused)."""

    message = "Only students can use this endpoint."

    def has_permission(self, request, view):
        return is_student(request.user)


class IsDocumentReviewer(BasePermission):
    """University administrators (or Django staff) only."""

    message = "Only university administrators can review documents."

    def has_permission(self, request, view):
        return is_document_reviewer(request.user)


class IsStudentOrDocumentReviewer(BasePermission):
    """Students (for their own files) and reviewers (for any file)."""

    message = "Only students and university administrators can download documents."

    def has_permission(self, request, view):
        return is_student(request.user) or is_document_reviewer(request.user)