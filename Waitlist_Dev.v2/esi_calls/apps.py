from django.apps import AppConfig

class EsiCallsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'esi_calls'
    verbose_name = 'ESI Calls'

    def ready(self):
        import esi_calls.signals
