from django.db import models
from django.contrib.auth.models import User
from pilot_data.models import ItemType

class Fleet(models.Model):
    """
    Represents an active fleet in the system.
    """
    name = models.CharField(max_length=100)
    commander = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='commanded_fleets')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

# --- DOCTRINE MODELS ---

class DoctrineTag(models.Model):
    """
    Custom labels for fits (e.g., 'Shield', 'Armor', 'Optimal', 'Sniper').
    Includes styling information for the frontend badge.
    """
    name = models.CharField(max_length=50, unique=True)
    # Tailwind classes for badge styling (e.g., "bg-blue-900/30 text-blue-400 border-blue-900/50")
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
    
    # The Hull (Linked to SDE)
    ship_type = models.ForeignKey(ItemType, on_delete=models.CASCADE, related_name='doctrines')
    
    # Store the raw text for easy "Copy to Clipboard"
    eft_format = models.TextField()
    
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tags to identify formatting style or specific roles (Logi, DPS)
    is_doctrinal = models.BooleanField(default=True)
    
    # Manual sorting
    order = models.IntegerField(default=0)

    # NEW: Tagging System
    tags = models.ManyToManyField(DoctrineTag, blank=True, related_name='fits')

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.ship_type.type_name} - {self.name}"

class FitModule(models.Model):
    """
    Individual items inside a fit. Used for advanced filtering later.
    """
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