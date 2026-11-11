from django.contrib import admin

from .models import AcademicYear


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ["label", "start_date", "end_date", "is_current"]
    list_filter = ["is_current"]
    search_fields = ["label"]