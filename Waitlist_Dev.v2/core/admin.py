from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Capability, Ban, BanAuditLog

class CustomUserAdmin(BaseUserAdmin):
    list_display = BaseUserAdmin.list_display + ('date_joined',)
    list_filter = BaseUserAdmin.list_filter + ('date_joined',)
    ordering = ('-date_joined',)

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(Capability)
class CapabilityAdmin(admin.ModelAdmin):
    # Added 'order' to display
    list_display = ('name', 'slug', 'category', 'order', 'get_group_count')
    # Made 'order' editable directly in the list view for convenience
    list_editable = ('order',)
    list_filter = ('category',)
    search_fields = ('name', 'slug', 'description')
    filter_horizontal = ('groups',)

    def get_group_count(self, obj):
        return obj.groups.count()
    get_group_count.short_description = 'Groups'

@admin.register(Ban)
class BanAdmin(admin.ModelAdmin):
    list_display = ('user', 'issuer', 'created_at', 'expires_at', 'is_active_display')
    list_filter = ('created_at', 'expires_at')
    search_fields = ('user__username', 'issuer__username', 'reason')
    autocomplete_fields = ['user', 'issuer']
    
    def is_active_display(self, obj):
        return obj.is_active
    is_active_display.boolean = True
    is_active_display.short_description = 'Active'

@admin.register(BanAuditLog)
class BanAuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action', 'target_user', 'actor', 'short_details')
    list_filter = ('action', 'timestamp')
    search_fields = ('target_user__username', 'actor__username', 'details')
    autocomplete_fields = ['target_user', 'actor']
    readonly_fields = ('timestamp',)

    def short_details(self, obj):
        return (obj.details[:75] + '...') if len(obj.details) > 75 else obj.details
    short_details.short_description = 'Details'