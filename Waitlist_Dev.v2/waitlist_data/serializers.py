from rest_framework import serializers
from .models import DoctrineCategory, DoctrineFit, FitModule, DoctrineTag

class DoctrineTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctrineTag
        fields = ['id', 'name', 'color']

class FitModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FitModule
        fields = ['id', 'name', 'quantity', 'is_cargo']

class DoctrineFitSerializer(serializers.ModelSerializer):
    tags = DoctrineTagSerializer(many=True, read_only=True)
    modules = FitModuleSerializer(many=True, read_only=True, source='fitmodule_set')
    
    # Add fields to get actual ship info instead of just the database ID
    # This allows us to fetch images and display the hull name
    hull_name = serializers.CharField(source='hull.name', read_only=True)
    hull_id = serializers.IntegerField(source='hull.id', read_only=True)

    class Meta:
        model = DoctrineFit
        fields = [
            'id', 'name', 'description', 'hull_name', 'hull_id', 'eft_format', 
            'is_active', 'order', 'tags', 'modules'
        ]

class DoctrineCategorySerializer(serializers.ModelSerializer):
    fits = serializers.SerializerMethodField()

    class Meta:
        model = DoctrineCategory
        fields = ['id', 'name', 'description', 'is_active', 'order', 'target_column', 'fits']

    def get_fits(self, obj):
        # Only return active fits for this category, ordered by their specific order
        fits = obj.fits.filter(is_active=True).order_by('order')
        return DoctrineFitSerializer(fits, many=True).data