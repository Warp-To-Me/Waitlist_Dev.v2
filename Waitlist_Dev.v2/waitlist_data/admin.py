from django.contrib import admin
from .models import Fleet, DoctrineCategory, DoctrineFit, FitModule, DoctrineTag, WaitlistEntry, FleetActivity

@admin.register(Fleet)
class FleetAdmin(admin.ModelAdmin):
    list_display = ('name', 'commander', 'is_active', 'created_at', 'join_token')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'commander__username')
    autocomplete_fields = ['commander']
    readonly_fields = ('join_token', 'created_at')

@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ('character', 'fleet', 'fit', 'status', 'time_waiting', 'created_at')
    list_filter = ('status', 'fleet__name', 'created_at')
    search_fields = ('character__character_name', 'fleet__name')
    autocomplete_fields = ['character', 'fleet', 'fit']
    readonly_fields = ('created_at', 'approved_at', 'invited_at')

@admin.register(FleetActivity)
class FleetActivityAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action', 'character', 'fleet', 'ship_name', 'actor')
    list_filter = ('action', 'fleet__name', 'timestamp')
    search_fields = ('character__character_name', 'fleet__name', 'actor__username', 'ship_name', 'details')
    autocomplete_fields = ['character', 'fleet', 'actor']
    readonly_fields = ('timestamp',)
    
    # Organize fields for better readability
    fieldsets = (
        ('Event Details', {
            'fields': ('action', 'timestamp', 'fleet', 'character')
        }),
        ('Context', {
            'fields': ('actor', 'ship_name', 'hull_id', 'details')
        }),
        ('Technical', {
            'fields': ('fit_eft',),
            'classes': ('collapse',)
        }),
    )

@admin.register(DoctrineTag)
class DoctrineTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'style_classes')
    list_editable = ('order', 'style_classes')

# --- DOCTRINE ADMIN ---

class FitModuleInline(admin.TabularInline):
    model = FitModule
    extra = 0
    autocomplete_fields = ['item_type'] 

@admin.register(DoctrineCategory)
class DoctrineCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'order', 'slug')
    list_editable = ('order',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    list_filter = ('parent',)
    ordering = ('parent__name', 'order', 'name')

@admin.register(DoctrineFit)
class DoctrineFitAdmin(admin.ModelAdmin):
    list_display = ('name', 'ship_type', 'category', 'is_doctrinal', 'order', 'updated_at')
    list_editable = ('order', 'is_doctrinal')
    list_filter = ('category', 'is_doctrinal', 'tags')
    search_fields = ('name', 'ship_type__type_name')
    inlines = [FitModuleInline]
    autocomplete_fields = ['ship_type']
    filter_horizontal = ('tags',)