import uuid
from django.db import models
from django.contrib.auth.models import User
from pilot_data.models import ItemType, EveCharacter

class Fleet(models.Model):
    name = models.CharField(max_length=100)
    commander = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='commanded_fleets')
    esi_fleet_id = models.BigIntegerField(null=True, blank=True)
    join_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    motd = models.TextField(blank=True, default="")
    status = models.CharField(max_length=100, blank=True, default="")
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

# --- FLEET STRUCTURE TEMPLATES ---

class FleetStructureTemplate(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name='fleet_templates')
    name = models.CharField(max_length=100, default="Default Setup")
    description = models.TextField(blank=True)
    default_motd = models.TextField(blank=True, default="")
    is_default = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.character.character_name})"

class StructureWing(models.Model):
    template = models.ForeignKey(FleetStructureTemplate, on_delete=models.CASCADE, related_name='wings')
    name = models.CharField(max_length=50)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

class StructureSquad(models.Model):
    wing = models.ForeignKey(StructureWing, on_delete=models.CASCADE, related_name='squads')
    name = models.CharField(max_length=50)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

# --- DOCTRINE MODELS ---

class DoctrineTag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    style_classes = models.CharField(max_length=255, default="bg-slate-700 text-slate-300 border-slate-600")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

class DoctrineCategory(models.Model):
    COLUMN_CHOICES = [
        ('inherit', 'Inherit (Child Priority)'),
        ('logi', 'Logistics'),
        ('dps', 'DPS'),
        ('sniper', 'Sniper'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    order = models.IntegerField(default=0)
    
    target_column = models.CharField(
        max_length=20, 
        choices=COLUMN_CHOICES, 
        default='inherit', 
        help_text="Where should ships in this category appear? 'Inherit' checks specific child settings first, then bubbles up to parent."
    )

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

# --- SKILL REQUIREMENTS & TIERS ---

class SkillGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class SkillGroupMember(models.Model):
    group = models.ForeignKey(SkillGroup, on_delete=models.CASCADE, related_name='members')
    skill = models.ForeignKey(ItemType, on_delete=models.CASCADE)
    level = models.IntegerField(default=1)

    class Meta:
        unique_together = ('group', 'skill')
        ordering = ['skill__type_name']

class SkillTier(models.Model):
    """
    Defines a level of skill compliance (e.g., Bronze, Silver, Gold, Elite).
    """
    name = models.CharField(max_length=50, unique=True)
    order = models.IntegerField(default=0, help_text="Higher number = Higher priority check.")
    badge_class = models.CharField(max_length=100, default="bg-yellow-500/20 text-yellow-400 border-yellow-500/50", help_text="Tailwind CSS classes for the badge.")
    hex_color = models.CharField(max_length=7, default="#EAB308", help_text="Hex color for glowing effects.")

    class Meta:
        ordering = ['-order'] # Highest first

    def __str__(self):
        return self.name

class SkillRequirement(models.Model):
    # Target can be a specific fit OR a generic hull
    doctrine_fit = models.ForeignKey(DoctrineFit, on_delete=models.CASCADE, null=True, blank=True, related_name='skill_requirements')
    hull = models.ForeignKey(ItemType, on_delete=models.CASCADE, null=True, blank=True, related_name='skill_requirements')
    
    # The requirement: Either a direct skill OR a group
    skill = models.ForeignKey(ItemType, on_delete=models.CASCADE, related_name='required_for_fits', null=True, blank=True)
    level = models.IntegerField(default=1, null=True, blank=True)
    
    group = models.ForeignKey(SkillGroup, on_delete=models.CASCADE, null=True, blank=True, related_name='required_by')
    
    # NEW: Tier association. Null = Minimum Requirement.
    tier = models.ForeignKey(SkillTier, on_delete=models.SET_NULL, null=True, blank=True, related_name='requirements')

    class Meta:
        ordering = ['skill__type_name', 'group__name']

    def __str__(self):
        target = self.doctrine_fit.name if self.doctrine_fit else (self.hull.type_name if self.hull else "Unknown")
        req = self.group.name if self.group else f"{self.skill.type_name} {self.level}"
        tier_str = f" [{self.tier.name}]" if self.tier else " [Min]"
        return f"{target} -> {req}{tier_str}"

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
    fit = models.ForeignKey(DoctrineFit, on_delete=models.SET_NULL, null=True, blank=True, related_name='active_entries')
    hull = models.ForeignKey(ItemType, on_delete=models.CASCADE, related_name='waitlist_entries_hull', null=True)
    raw_eft = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    invited_at = models.DateTimeField(null=True, blank=True)

    # Skills Status
    can_fly = models.BooleanField(default=True)
    missing_skills = models.JSONField(default=list, blank=True)
    
    # NEW: Matched Tier
    tier = models.ForeignKey(SkillTier, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        fit_name = self.fit.name if self.fit else "Custom Fit"
        return f"{self.character.character_name} - {fit_name}"
    
    @property
    def time_waiting(self):
        from django.utils import timezone
        diff = timezone.now() - self.created_at
        return int(diff.total_seconds() / 60)

# --- HISTORY LOGS ---

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
        ('ship_change', 'Changed Ship'),
        ('moved', 'Position Changed'),
        ('promoted', 'Promoted'),
        ('demoted', 'Demoted'),
        ('kicked', 'Kicked from Fleet')
    ]

    fleet = models.ForeignKey(Fleet, on_delete=models.CASCADE, related_name='activity_logs')
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name='fleet_history')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='actions_performed')
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ship_name = models.CharField(max_length=100, blank=True)
    hull_id = models.IntegerField(null=True, blank=True)
    fit_eft = models.TextField(blank=True, null=True)
    details = models.TextField(blank=True, null=True) 

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Fleet Activities"

    def __str__(self):
        return f"[{self.fleet.name}] {self.character.character_name} - {self.action}"

# --- NEW: STATS AGGREGATION MODEL ---

class CharacterStats(models.Model):
    """
    Stores aggregated service record data to avoid scanning FleetActivity logs on every request.
    Updated incrementally by fleet consumers.
    """
    character = models.OneToOneField(EveCharacter, on_delete=models.CASCADE, related_name='stats')
    total_seconds = models.BigIntegerField(default=0)
    
    # Stores per-ship stats: {"Megathron": 3600, "Guardian": 1200}
    hull_stats = models.JSONField(default=dict, blank=True)
    
    # Active Session Tracking
    # If not null, user is currently online in a fleet with this ship
    active_session_start = models.DateTimeField(null=True, blank=True)
    active_hull = models.CharField(max_length=100, null=True, blank=True)
    
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Stats: {self.character.character_name}"