from django.urls import re_path
from . import consumers as core_consumers
from waitlist_data import consumers as waitlist_consumers

websocket_urlpatterns = [
    re_path(r'ws/system/monitor/$', core_consumers.SystemMonitorConsumer.as_asgi()),
    # New Fleet Route
    re_path(r'ws/fleet/(?P<fleet_id>\d+)/$', waitlist_consumers.FleetConsumer.as_asgi()),
]