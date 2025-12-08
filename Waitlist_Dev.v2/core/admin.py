from django.contrib import admin
from .models import Capability

@admin.register(Capability)
class CapabilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'category', 'get_group_count')
    list_filter = ('category',)
    search_fields = ('name', 'slug', 'description')
    filter_horizontal = ('groups',)

    def get_group_count(self, obj):
        return obj.groups.count()
    get_group_count.short_description = 'Groups'