from rest_framework import generics
from waitlist_data.models import DoctrineCategory
from waitlist_data.serializers import DoctrineCategorySerializer

class PublicDoctrineListView(generics.ListAPIView):
    """
    Returns a list of active Doctrine Categories, each containing their active Fits.
    This is for the public doctrines page.
    """
    serializer_class = DoctrineCategorySerializer
    pagination_class = None  # We want all doctrines on one page usually

    def get_queryset(self):
        return DoctrineCategory.objects.filter(is_active=True).order_by('order')