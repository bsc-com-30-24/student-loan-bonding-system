"""Swagger helpers that keep the API docs organised without touching views.

Every endpoint is put into exactly one group, chosen by its URL. This stops
different teammates' tag names ("Documents (Students)", "bonds", "reports",
...) from showing up as duplicate or lowercase groups.
"""

import re

# (URL pattern, group). First match wins. In the schema, path parameters
# appear as {id}, {agreement_number}, and so on.
TAG_RULES = (
    (r"^/api/(register|token|password-reset)/", "Authentication"),
    (r"^/api/students/", "Students"),
    (r"^/api/loans/", "Loan Applications"),
    (r"^/api/my-documents/", "Documents - Student"),
    (r"^/api/\{[^}]+\}/download/", "Documents - Student"),
    (r"^/api/admin/documents/", "Documents - Admin"),
    (r"^/api/\{[^}]+\}/verify/", "Documents - Admin"),
    (r"^/api/my-notifications/", "Notifications"),
    (r"^/api/bonds/", "Bonds"),
    (r"^/api/agreements/", "Agreements"),
    (r"^/api/reports/", "Reports"),
    (r"^/api/verification/", "Verification"),
)

# Order and descriptions of the groups in Swagger and ReDoc. A group with no
# endpoints is not shown. This list replaces any TAGS block in settings.py.
SWAGGER_TAGS = [
    {
        "name": "Authentication",
        "description": "Register, log in, refresh tokens and reset passwords.",
    },
    {
        "name": "Students",
        "description": "Student details (registration number, programme, "
                       "academic information).",
    },
    {
        "name": "Loan Applications",
        "description": "Students apply for a loan (tuition and upkeep "
                       "amounts); the application is linked to the bond.",
    },
    {
        "name": "Documents - Student",
        "description": "Students upload, track and download their "
                       "supporting documents.",
    },
    {
        "name": "Documents - Admin",
        "description": "University administrators review, preview, verify or "
                       "reject documents.",
    },
    {
        "name": "Notifications",
        "description": "Students read notifications about document reviews "
                       "and bonds.",
    },
    {
        "name": "Bonds",
        "description": "Bonds per student and academic year, with history, "
                       "reviewed by university administrators.",
    },
    {
        "name": "Agreements",
        "description": "Generate, sign, countersign and download agreements.",
    },
    {
        "name": "Reports",
        "description": "Reports on active loans, defaulters and signed bonds.",
    },
    {
        "name": "Verification",
        "description": "Verify a student's bond status.",
    },
]

_COMPILED_RULES = [(re.compile(p), tag) for p, tag in TAG_RULES]


def tag_authentication_endpoints(result, generator, request, public):
    """drf-spectacular post-processing hook (name kept for settings.py)."""
    paths = result.get("paths", {})

    for path, path_item in paths.items():
        for pattern, tag in _COMPILED_RULES:
            if pattern.match(path):
                for operation in path_item.values():
                    if isinstance(operation, dict):
                        operation["tags"] = [tag]
                break

    used = {
        tag
        for path_item in paths.values()
        for operation in path_item.values()
        if isinstance(operation, dict)
        for tag in operation.get("tags", [])
    }

    listed = {tag["name"] for tag in SWAGGER_TAGS}
    result["tags"] = [tag for tag in SWAGGER_TAGS if tag["name"] in used] + [
        {"name": name} for name in sorted(used - listed)
    ]

    return result