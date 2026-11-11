"""Shared role checks for the whole project.

Every app (academics, documents, bonds, agreements, reporting) builds its
permissions from these, so a role means the same thing everywhere.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import UserProfile, get_user_role


def is_student(user):
    """A logged-in student (staff accounts are never students)."""
    return bool(
        user
        and user.is_authenticated
        and not user.is_staff
        and get_user_role(user) == UserProfile.Role.STUDENT
    )


def is_university_admin(user):
    """A university administrator (superusers and Django staff count too)."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or get_user_role(user) == UserProfile.Role.UNIVERSITY_ADMIN)
    )


def is_loan_board_officer(user):
    return bool(
        user
        and user.is_authenticated
        and get_user_role(user) == UserProfile.Role.LOAN_BOARD_OFFICER
    )


class IsStudentRole(BasePermission):
    message = "Only students can use this endpoint."

    def has_permission(self, request, view):
        return is_student(request.user)


class IsUniversityAdminOrBoardOfficer(BasePermission):
    """Staff-side readers: university administrators and loan board officers."""

    message = "Only university administrators and loan board officers can use this endpoint."

    def has_permission(self, request, view):
        return is_university_admin(request.user) or is_loan_board_officer(request.user)


class IsUniversityAdminOrReadOnly(BasePermission):
    """Any logged-in user may read; only university administrators may change."""

    message = "Only university administrators can change this."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return is_university_admin(user)