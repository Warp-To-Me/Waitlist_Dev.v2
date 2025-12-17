from django.urls import re_path
from . import consumers as core_consumers
from waitlist_data import consumers as waitlist_consumers

websocket_urlpatterns = [
    # System Admin Monitor
    re_path(r'^/?ws/system/monitor/$', core_consumers.SystemMonitorConsumer.as_asgi()),
    
    # Personal User Notifications (Rate Limits, Alerts)
    re_path(r'^/?ws/user/notify/$', core_consumers.UserConsumer.as_asgi()),
    
    # Script Console
    re_path(r'^/?ws/management/scripts/(?P<script_id>\w+)/?$', core_consumers.ScriptConsumer.as_asgi()),
    
    # Fleet Dashboard
    re_path(r'^/?ws/fleet/(?P<token>[0-9a-f-]+)/$', waitlist_consumers.FleetConsumer.as_asgi()),
]
