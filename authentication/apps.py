from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "authentication"

    def ready(self):
        # Registers the Swagger description for the token refresh endpoint.
        from . import schema  # noqa: F401