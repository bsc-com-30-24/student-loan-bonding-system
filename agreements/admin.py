from django.contrib import admin
from .models import Agreement


@admin.register(Agreement)
class AgreementAdmin(admin.ModelAdmin):
    list_display = (
        'agreement_number',
        'student_id',
        'loan_reference',
        'status',
        'generated_at',
    )

    list_filter = ('status', 'generated_at')

    search_fields = (
        'student_id',
        'loan_reference',
    )