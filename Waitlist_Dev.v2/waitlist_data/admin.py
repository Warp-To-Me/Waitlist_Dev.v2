from django.contrib import admin
from .models import Fleet, DoctrineCategory, DoctrineFit, FitModule

@admin.register(Fleet)
class FleetAdmin(admin.ModelAdmin):
    list_display = ('name', 'commander', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'commander__username')
    autocomplete_fields = ['commander']

# --- DOCTRINE ADMIN ---

class FitModuleInline(admin.TabularInline):
    model = FitModule
    extra = 0
    # Uses the search capability of ItemTypeAdmin to load items fast
    autocomplete_fields = ['item_type'] 

@admin.register(DoctrineCategory)
class DoctrineCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'order')
    list_editable = ('order',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(DoctrineFit)
class DoctrineFitAdmin(admin.ModelAdmin):
    list_display = ('name', 'ship_type', 'category', 'is_doctrinal', 'updated_at')
    list_filter = ('category', 'is_doctrinal')
    search_fields = ('name', 'ship_type__type_name')
    inlines = [FitModuleInline]
    # Uses the search capability of ItemTypeAdmin
    autocomplete_fields = ['ship_type']