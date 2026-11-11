from django.db import transaction
from django.utils import timezone

from .models import AcademicYear


def get_current_academic_year():
    """The year new applications and bonds belong to.

    Creates a year labelled with the calendar year (for example 2026) when
    none has been marked current yet.
    """
    current = (
        AcademicYear.objects.filter(is_current=True).order_by("-label").first()
    )
    if current is not None:
        return current

    label = str(timezone.now().year)
    with transaction.atomic():
        year, _created = AcademicYear.objects.get_or_create(
            label=label,
            defaults={"is_current": True},
        )
        if not year.is_current and not AcademicYear.objects.filter(
            is_current=True
        ).exists():
            year.is_current = True
            year.save(update_fields=["is_current"])
        return year


def get_or_create_academic_year(label):
    """Return the year for a label such as 2026 or 2025/2026."""
    cleaned = str(label).strip()
    year, _created = AcademicYear.objects.get_or_create(label=cleaned)
    return year
