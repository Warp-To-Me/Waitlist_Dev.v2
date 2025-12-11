from django.db import models
from django.contrib.auth.models import Group, User
from django.utils import timezone

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

class Ban(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bans')
    issuer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='bans_issued')
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Track if we have logged the expiration event to avoid duplicates
    expiration_logged = models.BooleanField(default=False)

    @property
    def is_active(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def __str__(self):
        return f"Ban: {self.user.username}"

class BanAuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Ban Created'),
        ('update', 'Ban Updated'),
        ('remove', 'Ban Removed'),
        ('expire', 'Ban Expired'),
    ]

    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ban_logs')
    ban = models.ForeignKey(Ban, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ban_actions')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} - {self.target_user}"