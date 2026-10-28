from rest_framework.permissions import BasePermission

from .models import UserProfile, get_user_role


ALL_ROLES = frozenset(UserProfile.Role.values)
LOAN_READER_ROLES = frozenset(
    {
        UserProfile.Role.STUDENT,
        UserProfile.Role.UNIVERSITY_ADMIN,
        UserProfile.Role.LOAN_BOARD_OFFICER,
    }
)


class HasRolePermission(BasePermission):
    action_roles = {
        "metadata": ALL_ROLES,
        "list": LOAN_READER_ROLES,
        "retrieve": LOAN_READER_ROLES,
        "create": frozenset({UserProfile.Role.STUDENT}),
        "update": frozenset(
            {UserProfile.Role.STUDENT, UserProfile.Role.LOAN_BOARD_OFFICER}
        ),
        "partial_update": frozenset(
            {UserProfile.Role.STUDENT, UserProfile.Role.LOAN_BOARD_OFFICER}
        ),
        "destroy": frozenset({UserProfile.Role.STUDENT}),
    }

    def has_permission(self, request, view):
        role = get_user_role(request.user)
        action = getattr(view, "action", None)
        allowed_roles = getattr(view, "allowed_roles", None)
        if allowed_roles is not None:
            return role in allowed_roles
        return role in self.action_roles.get(action, frozenset())