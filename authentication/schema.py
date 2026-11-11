"""Swagger documentation for third-party views we do not own."""
from drf_spectacular.extensions import OpenApiViewExtension
from drf_spectacular.utils import extend_schema


class TokenRefreshViewExtension(OpenApiViewExtension):
    target_class = "rest_framework_simplejwt.views.TokenRefreshView"

    def view_replacement(self):
        @extend_schema(
            tags=["Authentication"],
            summary="Refresh access token",
            description=(
                "Exchanges a valid refresh token for a new short-lived access "
                "token, so the user does not have to log in again. Send the "
                "refresh value returned by the login endpoint."
            ),
        )
        class Fixed(self.target_class):
            pass

        return Fixed


# Order of the sections in Swagger. Matched on the start of the tag name
# (case-insensitive), so "Bonds" and "Bonds (Students)" both land in slot 4.
# Anything not listed goes after these, alphabetically.
TAG_ORDER = (
    "authentication",
    "documents (student",
    "documents (admin",
    "bond",
    "agreement",
)


def _tag_rank(name):
    lowered = name.lower()
    for rank, prefix in enumerate(TAG_ORDER):
        if lowered.startswith(prefix):
            return rank
    return len(TAG_ORDER)


def order_tags(result, generator, request, public):
    """drf-spectacular post-processing hook: sort the Swagger sections."""
    tags = {tag["name"]: tag for tag in result.get("tags", [])}
    for path_item in result.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                for name in operation.get("tags", []):
                    tags.setdefault(name, {"name": name})

    result["tags"] = sorted(
        tags.values(), key=lambda tag: (_tag_rank(tag["name"]), tag["name"].lower())
    )
    return result