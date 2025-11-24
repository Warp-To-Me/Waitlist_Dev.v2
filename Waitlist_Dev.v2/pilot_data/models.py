from django.db import models
from django.contrib.auth.models import User

class EveCharacter(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='characters')
    character_id = models.BigIntegerField(unique=True)
    character_name = models.CharField(max_length=255)
    is_main = models.BooleanField(default=False)
    
    corporation_id = models.BigIntegerField(default=0)
    corporation_name = models.CharField(max_length=255, blank=True, default="")
    alliance_id = models.BigIntegerField(null=True, blank=True)
    alliance_name = models.CharField(max_length=255, blank=True, default="")
    
    total_sp = models.BigIntegerField(default=0)
    current_ship_name = models.CharField(max_length=255, blank=True, default="")
    current_ship_type_id = models.IntegerField(null=True, blank=True)
    
    access_token = models.TextField(blank=True, default="")
    refresh_token = models.TextField(blank=True, default="")
    token_expires = models.DateTimeField(null=True, blank=True)
    
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.character_name} ({self.character_id})"

class EsiHeaderCache(models.Model):
    """
    Stores ESI Caching headers (ETag / Expires) to prevent redundant API calls.
    """
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name='esi_headers')
    endpoint_name = models.CharField(max_length=100, db_index=True) 
    etag = models.CharField(max_length=255, blank=True, null=True)
    expires = models.DateTimeField(null=True, blank=True)
    
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
    corporation_name = models.CharField(max_length=255, blank=True, default="Unknown Corp") # New Field
    start_date = models.DateTimeField()

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
    group_id = models.IntegerField() 
    type_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    mass = models.FloatField(default=0)
    volume = models.FloatField(default=0)
    capacity = models.FloatField(default=0)
    published = models.BooleanField(default=True)
    market_group_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.type_name