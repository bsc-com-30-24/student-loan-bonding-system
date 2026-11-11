from django.db import models, transaction
from django.db.models import F, Q


class AcademicYear(models.Model):
    """One academic year (e.g. "2026"). Bonds, agreements and documents hang off it.

    Years are never deleted once records point at them (on_delete=PROTECT on
    the other side), so the history of each year is always kept.
    """

    label = models.CharField(
        max_length=20,
        unique=True,
        help_text='Name of the year, for example "2026" or "2026/2027".',
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(
        default=False,
        help_text="The year new applications and documents go into. Only one year is current.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-label"]
        constraints = [
            # The database itself guarantees a single current year.
            models.UniqueConstraint(
                fields=["is_current"],
                condition=Q(is_current=True),
                name="only_one_current_academic_year",
            ),
            models.CheckConstraint(
                condition=(
                    Q(start_date__isnull=True)
                    | Q(end_date__isnull=True)
                    | Q(end_date__gt=F("start_date"))
                ),
                name="academic_year_ends_after_it_starts",
            ),
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_current:
                # Making this year current retires the previous current year.
                AcademicYear.objects.exclude(pk=self.pk).filter(
                    is_current=True
                ).update(is_current=False)
            super().save(*args, **kwargs)

    @classmethod
    def get_current(cls):
        return cls.objects.filter(is_current=True).first()

    def __str__(self):
        return self.label