from rest_framework import serializers

from .models import AcademicYear


class AcademicYearSerializer(serializers.ModelSerializer):
    # Declared by hand so DRF does not attach its own "only one current year" check,
    # which would fire before the model retires the previous current year.
    is_current = serializers.BooleanField(
        required=False,
        default=False,
        help_text=(
            "Make this the current year. The previous current year is retired "
            "automatically."
        ),
    )

    class Meta:
        model = AcademicYear
        fields = ["id", "label", "start_date", "end_date", "is_current", "created_at"]
        read_only_fields = ["id", "created_at"]
        # DRF would reject a second is_current=True before the model gets to retire
        # the old current year. The model and a database constraint enforce it instead
        # (label uniqueness is still checked on the field itself).
        validators = []
        extra_kwargs = {
            "label": {"help_text": 'Name of the year, e.g. "2026" or "2026/2027".'},
            "start_date": {"help_text": "First day of the academic year (optional)."},
            "end_date": {"help_text": "Last day of the academic year (optional)."},
        }

    def validate_label(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("The academic year needs a label.")
        return value

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": "The end date must be after the start date."}
            )
        return attrs