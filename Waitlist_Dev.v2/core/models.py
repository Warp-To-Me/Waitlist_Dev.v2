from django.db import models
from django.contrib.auth.models import Group

class Capability(models.Model):
    """
    Represents a system permission/capability that can be assigned to Groups.
    """
    slug = models.SlugField(unique=True, help_text="Internal identifier used in code checks (e.g. 'fleet_command')")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, default="General")
    groups = models.ManyToManyField(Group, related_name='capabilities', blank=True)

    class Meta:
        verbose_name_plural = "Capabilities"
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.slug})"

class RolePriority(models.Model):
    """
    Extension of Django Group to store hierarchy order.
    Lower 'priority' integer = Higher Rank (e.g. Admin = 0).
    """
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='priority_config')
    level = models.IntegerField(default=999, db_index=True)

    class Meta:
        ordering = ['level']

    def __str__(self):
        return f"{self.group.name} (Lvl {self.level})"