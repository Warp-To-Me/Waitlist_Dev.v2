from django.db import models
from django.contrib.auth.models import User
from fernet_fields import EncryptedTextField

class EveCharacter(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='characters')
    character_id = models.BigIntegerField(unique=True)
    character_name = models.CharField(max_length=255)
    is_main = models.BooleanField(default=False)
    
    # Controls visibility in the X-Up Modal
    x_up_visible = models.BooleanField(default=True)

    # Aggregate Inclusion Flags
    include_wallet_in_aggregate = models.BooleanField(default=True)
    include_lp_in_aggregate = models.BooleanField(default=True)
    include_sp_in_aggregate = models.BooleanField(default=True)
    
    corporation_id = models.BigIntegerField(default=0)
    corporation_name = models.CharField(max_length=255, blank=True, default="")
    alliance_id = models.BigIntegerField(null=True, blank=True)
    alliance_name = models.CharField(max_length=255, blank=True, default="")
    
    total_sp = models.BigIntegerField(default=0)
    current_ship_name = models.CharField(max_length=255, blank=True, default="")
    current_ship_type_id = models.IntegerField(null=True, blank=True)

    # Financials
    wallet_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    concord_lp = models.IntegerField(default=0)
    
    # Activity Tracking
    is_online = models.BooleanField(default=False)
    last_login_at = models.DateTimeField(null=True, blank=True)
    last_online_at = models.DateTimeField(null=True, blank=True)

    # Encrypted Fields
    access_token = EncryptedTextField(blank=True, default="")
    refresh_token = EncryptedTextField(blank=True, default="")
    
    token_expires = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    # Scopes
    granted_scopes = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.character_name} ({self.character_id})"

class EsiHeaderCache(models.Model):
    """
    Stores ESI Caching headers (ETag / Expires) to prevent redundant API calls.
    """
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name='esi_headers')
    endpoint_name = models.CharField(max_length=100, db_index=True) 
    etag = models.CharField(max_length=255, blank=True, null=True)
    expires = models.DateTimeField(null=True, blank=True, db_index=True)
    
    class Meta:
        unique_together = ('character', 'endpoint_name')

class CharacterSkill(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name='skills')
    skill_id = models.IntegerField()
    active_skill_level = models.IntegerField()
    skillpoints_in_skill = models.BigIntegerField()

class CharacterQueue(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name='skill_queue')
    skill_id = models.IntegerField()
    finished_level = models.IntegerField()
    queue_position = models.IntegerField()
    finish_date = models.DateTimeField(null=True, blank=True)

class CharacterImplant(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name='implants')
    type_id = models.IntegerField()

class CharacterHistory(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name='corp_history')
    corporation_id = models.IntegerField()
    corporation_name = models.CharField(max_length=255, blank=True, default="Unknown Corp")
    start_date = models.DateTimeField()

class SkillHistory(models.Model):
    """
    Logs changes to skills (training complete, injection, etc.)
    """
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name='skill_history')
    skill_id = models.IntegerField()
    old_level = models.IntegerField()
    new_level = models.IntegerField()
    old_sp = models.BigIntegerField()
    new_sp = models.BigIntegerField()
    logged_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"History: {self.character.character_name} Skill {self.skill_id}"

# --- SDE Models ---

class ItemGroup(models.Model):
    group_id = models.IntegerField(primary_key=True)
    category_id = models.IntegerField()
    group_name = models.CharField(max_length=255)
    published = models.BooleanField(default=True)

    def __str__(self):
        return self.group_name

class ItemType(models.Model):
    type_id = models.IntegerField(primary_key=True)
    group = models.ForeignKey(ItemGroup, on_delete=models.CASCADE, related_name='types', db_column='group_id', null=True)
    type_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    mass = models.FloatField(default=0)
    volume = models.FloatField(default=0)
    capacity = models.FloatField(default=0)
    published = models.BooleanField(default=True)
    market_group_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.type_name

    def get_attribute(self, attr_id):
        try:
            return self.attributes.get(attribute_id=attr_id).value
        except TypeAttribute.DoesNotExist:
            return 0

    @property
    def high_slots(self): return int(self.get_attribute(14))
    
    @property
    def mid_slots(self): return int(self.get_attribute(13))
    
    @property
    def low_slots(self): return int(self.get_attribute(12))

    @property
    def rig_slots(self): return int(self.get_attribute(1137))

class TypeAttribute(models.Model):
    """
    Links an ItemType to a Dogma Attribute (e.g., Ship -> High Slot Count).
    """
    item = models.ForeignKey(ItemType, on_delete=models.CASCADE, related_name='attributes')
    attribute_id = models.IntegerField(db_index=True)
    value = models.FloatField()

    class Meta:
        unique_together = ('item', 'attribute_id') 
        indexes = [
            models.Index(fields=['item', 'attribute_id']),
        ]

    def __str__(self):
        return f"Item {self.item.type_id} - Attr {self.attribute_id}: {self.value}"

class TypeEffect(models.Model):
    """
    Links an ItemType to a Dogma Effect.
    Crucial for determining if an item is High/Mid/Low slot.
    """
    item = models.ForeignKey(ItemType, on_delete=models.CASCADE, related_name='effects')
    effect_id = models.IntegerField(db_index=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = ('item', 'effect_id')
        indexes = [
            models.Index(fields=['item', 'effect_id']),
        ]

    def __str__(self):
        return f"Item {self.item.type_id} - Effect {self.effect_id}"

# --- FIT ANALYSIS MODELS ---

class AttributeDefinition(models.Model):
    """
    Stores human-readable names for SDE attributes (e.g. 50 -> 'CPU Usage').
    """
    attribute_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    display_name = models.CharField(max_length=255, blank=True, null=True)
    unit_id = models.IntegerField(null=True, blank=True)
    published = models.BooleanField(default=True)

    def __str__(self):
        return self.display_name or self.name

class FitAnalysisRule(models.Model):
    """
    Defines which attributes matter for a specific Item Group.
    """
    group = models.ForeignKey(ItemGroup, on_delete=models.CASCADE, related_name='analysis_rules')
    attribute = models.ForeignKey(AttributeDefinition, on_delete=models.CASCADE)
    
    priority = models.IntegerField(default=0, help_text="Order of importance (higher first)")
    comparison_logic = models.CharField(
        max_length=20, 
        choices=[
            ('higher', 'Higher is Better'),
            ('lower', 'Lower is Better'),
            ('match', 'Must Match Exactly')
        ],
        default='higher'
    )
    tolerance_percent = models.FloatField(default=0.0, help_text="Percentage difference allowed before flagging as downgrade")

    class Meta:
        unique_together = ('group', 'attribute')
        ordering = ['group', '-priority']

    def __str__(self):
        return f"{self.group.group_name}: {self.attribute.name}"

# --- NEW SRP & WALLET MODELS ---

class SRPConfiguration(models.Model):
    """
    Singleton-style model to store which character is the source of SRP data.
    """
    character = models.OneToOneField(EveCharacter, on_delete=models.CASCADE, related_name='srp_config')
    last_sync = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"SRP Source: {self.character.character_name}"

class CorpWalletJournal(models.Model):
    """
    Cached journal entries for analytics.
    """
    config = models.ForeignKey(SRPConfiguration, on_delete=models.CASCADE, related_name='journal_entries')
    entry_id = models.BigIntegerField(unique=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    balance = models.DecimalField(max_digits=20, decimal_places=2)
    context_id = models.BigIntegerField(null=True, blank=True)
    context_id_type = models.CharField(max_length=50, null=True, blank=True)
    date = models.DateTimeField(db_index=True)
    description = models.TextField()
    first_party_id = models.IntegerField(null=True)
    second_party_id = models.IntegerField(null=True)
    reason = models.TextField(blank=True)
    ref_type = models.CharField(max_length=50)
    tax = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    division = models.IntegerField(default=1, db_index=True) # 1-7 master wallets

    # Enriched Data (Resolved Names)
    first_party_name = models.CharField(max_length=255, blank=True)
    second_party_name = models.CharField(max_length=255, blank=True)
    
    # NEW: Custom Category for manual tracking / historical import (Index 17 in SQL)
    custom_category = models.CharField(max_length=50, blank=True, null=True, db_index=True)

    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date', 'division']),
            models.Index(fields=['ref_type']),
            models.Index(fields=['custom_category']), # Index for analytics
        ]