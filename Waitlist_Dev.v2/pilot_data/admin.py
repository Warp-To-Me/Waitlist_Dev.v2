from django.contrib import admin
from .models import EveCharacter, ItemType, ItemGroup, AttributeDefinition, FitAnalysisRule

@admin.register(EveCharacter)
class EveCharacterAdmin(admin.ModelAdmin):
    list_display = ('character_name', 'user', 'is_main', 'corporation_name', 'total_sp', 'last_updated')
    list_filter = ('is_main',)
    search_fields = ('character_name', 'user__username', 'corporation_name')
    ordering = ('-last_updated',)

@admin.register(ItemType)
class ItemTypeAdmin(admin.ModelAdmin):
    list_display = ('type_name', 'type_id', 'group_id', 'published')
    list_filter = ('published',)
    search_fields = ('type_name',) # Required for autocomplete_fields to work elsewhere
    ordering = ('type_name',)

@admin.register(ItemGroup)
class ItemGroupAdmin(admin.ModelAdmin):
    list_display = ('group_name', 'group_id', 'category_id', 'published')
    search_fields = ('group_name',)
    list_filter = ('published',)

@admin.register(AttributeDefinition)
class AttributeDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'attribute_id', 'display_name', 'published', 'unit_id')
    search_fields = ('name', 'display_name', 'attribute_id')
    list_filter = ('published',)
    ordering = ('name',)

@admin.register(FitAnalysisRule)
class FitAnalysisRuleAdmin(admin.ModelAdmin):
    list_display = ('group', 'attribute', 'comparison_logic', 'priority')
    list_filter = ('comparison_logic', 'group')
    autocomplete_fields = ['group', 'attribute'] # Uses search_fields from ItemGroup and AttributeDefinition
    ordering = ('group', '-priority')