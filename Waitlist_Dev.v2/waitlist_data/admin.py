from django.contrib import admin
from .models import Fleet, DoctrineCategory, DoctrineFit, FitModule, DoctrineTag

@admin.register(Fleet)
class FleetAdmin(admin.ModelAdmin):
    list_display = ('name', 'commander', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'commander__username')
    autocomplete_fields = ['commander']

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
    filter_horizontal = ('tags',) # Improved UI for M2M selection