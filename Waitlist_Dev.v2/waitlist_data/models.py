import uuid
from django.db import models
from django.contrib.auth.models import User
from pilot_data.models import ItemType, EveCharacter

class Fleet(models.Model):
    """
    Represents an active fleet session.
    """
    name = models.CharField(max_length=100)
    commander = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='commanded_fleets')
    
    # ESI Fleet ID (For tracking in-game status)
    esi_fleet_id = models.BigIntegerField(null=True, blank=True)
    
    # PUBLIC JOIN TOKEN (UUID)
    # used for URLs instead of the integer ID to prevent guessing
    join_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} (FC: {self.commander.username if self.commander else 'None'})"

    @property
    def duration(self):
        from django.utils import timezone
        end = self.end_time or timezone.now()
        return end - self.created_at

# --- DOCTRINE MODELS (Existing) ---

class DoctrineTag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    style_classes = models.CharField(max_length=255, default="bg-slate-700 text-slate-300 border-slate-600")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

class DoctrineCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    order = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = "Doctrine Categories"
        ordering = ['order', 'name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} -> {self.name}"
        return self.name

class DoctrineFit(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(DoctrineCategory, on_delete=models.CASCADE, related_name='fits')
    ship_type = models.ForeignKey(ItemType, on_delete=models.CASCADE, related_name='doctrines')
    eft_format = models.TextField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_doctrinal = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    tags = models.ManyToManyField(DoctrineTag, blank=True, related_name='fits')

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.ship_type.type_name} - {self.name}"

class FitModule(models.Model):
    SLOT_CHOICES = [
        ('high', 'High Slot'),
        ('mid', 'Mid Slot'),
        ('low', 'Low Slot'),
        ('rig', 'Rig Slot'),
        ('subsystem', 'Subsystem'),
        ('drone', 'Drone Bay'),
        ('cargo', 'Cargo'),
    ]

    fit = models.ForeignKey(DoctrineFit, on_delete=models.CASCADE, related_name='modules')
    item_type = models.ForeignKey(ItemType, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    slot = models.CharField(max_length=20, choices=SLOT_CHOICES, default='cargo')

    def __str__(self):
        return f"{self.quantity}x {self.item_type.type_name}"

# --- WAITLIST ENTRIES ---

class WaitlistEntry(models.Model):
    STATUS_CHOICES = [
        ('pending', 'X-Up (Pending)'),
        ('approved', 'Approved'),
        ('invited', 'Invited'),
        ('rejected', 'Rejected'),
    ]

    fleet = models.ForeignKey(Fleet, on_delete=models.CASCADE, related_name='entries')
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name='waitlist_entries')
    fit = models.ForeignKey(DoctrineFit, on_delete=models.SET_NULL, null=True, related_name='active_entries')
    
    # Store the actual paste the user provided
    raw_eft = models.TextField(blank=True, default="")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    approved_at = models.DateTimeField(null=True, blank=True)
    invited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.character.character_name} - {self.fit.name if self.fit else 'No Fit'}"
    
    @property
    def time_waiting(self):
        from django.utils import timezone
        diff = timezone.now() - self.created_at
        return int(diff.total_seconds() / 60)

# --- HISTORY & AUDIT LOGS (New) ---

class FleetActivity(models.Model):
    ACTION_TYPES = [
        ('x_up', 'X-Up (Joined Waitlist)'),
        ('approved', 'Approved by FC'),
        ('denied', 'Denied by FC'),
        ('invited', 'Invited to Fleet'),
        ('esi_join', 'Joined Fleet (In-Game)'),
        ('left_waitlist', 'Left Waitlist'),
        ('left_fleet', 'Left Fleet (In-Game)'),
        ('fit_update', 'Updated Fit'),
        ('ship_change', 'Changed Ship'), # NEW
        ('moved', 'Position Changed'),
        ('promoted', 'Promoted'),
        ('demoted', 'Demoted'),
        ('kicked', 'Kicked from Fleet')
    ]

    fleet = models.ForeignKey(Fleet, on_delete=models.CASCADE, related_name='activity_logs')
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name='fleet_history')
    
    # Who performed the action? (e.g. FC invited Pilot)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='actions_performed')
    
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Snapshots for metrics
    ship_name = models.CharField(max_length=100, blank=True) # Hull name e.g. "Megathron"
    hull_id = models.IntegerField(null=True, blank=True)
    
    # Store the RAW EFT for historical inspection
    fit_eft = models.TextField(blank=True, null=True)
    
    # JSON for extra details (e.g. fit name, specific slot changes)
    details = models.TextField(blank=True, null=True) 

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Fleet Activities"

    def __str__(self):
        return f"[{self.fleet.name}] {self.character.character_name} - {self.action}"