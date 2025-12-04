from django.core.management.base import BaseCommand
import pandas as pd
import requests
import io
from pilot_data.models import ItemType, ItemGroup, TypeAttribute

class Command(BaseCommand):
    help = 'Imports Eve Online Static Data Export (SDE) items, groups, and attributes.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting SDE Import...'))
        
        # 1. Groups
        self.import_inv_groups()
        
        # 2. Types
        self.import_inv_types()
        
        # 3. Attributes (Published Only)
        self.import_dogma_attributes()
        
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

    def import_dogma_attributes(self):
        """
        1. Downloads dgmAttributeTypes.csv to find which Attributes are 'published'.
        2. Downloads dgmTypeAttributes.csv and filters rows against that whitelist.
        """
        # Step 1: Get the Definition Whitelist
        def_url = "https://www.fuzzwork.co.uk/dump/latest/dgmAttributeTypes.csv"
        self.stdout.write(f"Fetching Attribute Definitions from {def_url}...")
        
        published_attr_ids = set()
        
        try:
            resp = requests.get(def_url)
            resp.raise_for_status()
            df_defs = pd.read_csv(io.StringIO(resp.content.decode('utf-8')))
            
            # Filter for published=1
            if 'published' in df_defs.columns:
                published_attr_ids = set(df_defs[df_defs['published'] == 1]['attributeID'])
                self.stdout.write(f" -> Found {len(published_attr_ids)} published attribute definitions.")
            else:
                self.stdout.write(self.style.WARNING(" -> 'published' column missing. Defaulting to ALL attributes."))
                published_attr_ids = set(df_defs['attributeID'])

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to fetch definitions: {e}"))
            return

        # Step 2: Get Values and Filter
        val_url = "https://www.fuzzwork.co.uk/dump/latest/dgmTypeAttributes.csv"
        self.stdout.write(f"Downloading Item Attributes from {val_url}...")
        
        try:
            response = requests.get(val_url)
            response.raise_for_status()
            
            csv_content = io.StringIO(response.content.decode('utf-8'))
            df = pd.read_csv(csv_content)
            
            # THE FILTER: Keep only if attributeID is in our whitelist
            df_filtered = df[df['attributeID'].isin(published_attr_ids)]
            
            self.stdout.write(f"Processing {len(df_filtered)} attributes (Filtered from {len(df)})...")
            
            attrs_to_create = []
            
            # Get set of valid ItemIDs to avoid foreign key errors
            valid_type_ids = set(ItemType.objects.values_list('type_id', flat=True))

            for row in df_filtered.itertuples():
                if row.typeID not in valid_type_ids:
                    continue

                attrs_to_create.append(
                    TypeAttribute(
                        item_id=row.typeID,
                        attribute_id=row.attributeID,
                        value=row.valueFloat if pd.notna(row.valueFloat) else (row.valueInt if pd.notna(row.valueInt) else 0.0)
                    )
                )
                
                if len(attrs_to_create) >= 5000:
                    TypeAttribute.objects.bulk_create(attrs_to_create, ignore_conflicts=True)
                    attrs_to_create = []
                    # self.stdout.write(".", ending="")

            if attrs_to_create:
                TypeAttribute.objects.bulk_create(attrs_to_create, ignore_conflicts=True)
                
            self.stdout.write(self.style.SUCCESS("\nAttribute Import complete."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing Attributes: {e}"))