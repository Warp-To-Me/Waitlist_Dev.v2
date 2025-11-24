from django.db import models
from django.contrib.auth.models import User

class Fleet(models.Model):
    """
    Represents an active fleet in the system.
    """
    name = models.CharField(max_length=100)
    commander = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='commanded_fleets')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Link to a system ID or constellation ID from SDE in the future
    # location_id = ... 
    
    def __str__(self):
        return self.name

# Future models: WaitlistEntry, WaitlistGroup