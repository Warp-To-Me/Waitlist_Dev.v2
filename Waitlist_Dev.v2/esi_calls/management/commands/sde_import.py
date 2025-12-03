from django.core.management.base import BaseCommand
import pandas as pd
import requests
import io
from pilot_data.models import ItemType, ItemGroup

class Command(BaseCommand):
    help = 'Imports Eve Online Static Data Export (SDE) items and groups from Fuzzworks.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting SDE Import...'))
        
        # Run the import logic
        self.import_inv_groups()
        self.import_inv_types()
        
        self.stdout.write(self.style.SUCCESS('Full SDE Import Complete.'))

    def import_inv_groups(self):
        """
        Downloads invGroups.csv from Fuzzworks and imports it.
        """
        url = "https://www.fuzzwork.co.uk/dump/latest/invGroups.csv"
        self.stdout.write(f"Downloading Groups from {url}...")
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            csv_content = io.StringIO(response.content.decode('utf-8'))
            df = pd.read_csv(csv_content)
            
            self.stdout.write(f"Processing {len(df)} groups...")
            groups_to_create = []
            
            for row in df.itertuples():
                # Safety check for published attribute
                published = bool(row.published) if hasattr(row, 'published') else True
                
                groups_to_create.append(
                    ItemGroup(
                        group_id=row.groupID,
                        category_id=row.categoryID,
                        group_name=row.groupName,
                        published=published
                    )
                )
                if len(groups_to_create) >= 1000:
                    ItemGroup.objects.bulk_create(groups_to_create, ignore_conflicts=True)
                    groups_to_create = []
            
            if groups_to_create:
                ItemGroup.objects.bulk_create(groups_to_create, ignore_conflicts=True)
                
            self.stdout.write(self.style.SUCCESS("Group Import complete."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing Groups: {e}"))

    def import_inv_types(self):
        """
        Downloads invTypes.csv from Fuzzworks and imports it.
        """
        url = "https://www.fuzzwork.co.uk/dump/latest/invTypes.csv"
        
        self.stdout.write(f"Downloading Items from {url}...")
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            # Read CSV content
            csv_content = io.StringIO(response.content.decode('utf-8'))
            
            # Load into Pandas DataFrame
            df = pd.read_csv(csv_content)
            
            self.stdout.write(f"Processing {len(df)} records...")
            
            items_to_create = []
            
            for row in df.itertuples():
                items_to_create.append(
                    ItemType(
                        type_id=row.typeID,
                        group_id=row.groupID,
                        type_name=row.typeName,
                        description=row.description if hasattr(row, 'description') and pd.notna(row.description) else "",
                        mass=row.mass if hasattr(row, 'mass') else 0,
                        volume=row.volume if hasattr(row, 'volume') else 0,
                        capacity=row.capacity if hasattr(row, 'capacity') else 0,
                        published=bool(row.published) if hasattr(row, 'published') else True,
                        market_group_id=row.marketGroupID if hasattr(row, 'marketGroupID') and pd.notna(row.marketGroupID) else None
                    )
                )
                
                if len(items_to_create) >= 1000:
                    ItemType.objects.bulk_create(items_to_create, ignore_conflicts=True)
                    items_to_create = []
            
            if items_to_create:
                ItemType.objects.bulk_create(items_to_create, ignore_conflicts=True)
                
            self.stdout.write(self.style.SUCCESS("Item Import complete."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing SDE: {e}"))