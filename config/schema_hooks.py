"""Swagger helpers that keep the API docs organised without touching views."""

# Every endpoint under these paths is shown in the "Authentication" group.
AUTH_PATH_PREFIXES = (
    "/api/register/",
    "/api/token/",
    "/api/password-reset/",
)


def tag_authentication_endpoints(result, generator, request, public):
    """drf-spectacular post-processing hook."""
    for path, path_item in result.get("paths", {}).items():
        if not path.startswith(AUTH_PATH_PREFIXES):
            continue

        for operation in path_item.values():
            if isinstance(operation, dict):
                operation["tags"] = ["Authentication"]

    return result