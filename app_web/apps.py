from django.apps import AppConfig


class AppWebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_web'

    def ready(self):
        # Import signals so receivers get registered
        from . import signals  # noqa: F401
