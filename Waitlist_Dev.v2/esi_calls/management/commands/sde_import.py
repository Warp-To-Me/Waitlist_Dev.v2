from django.core.management.base import BaseCommand
import pandas as pd
import requests
import io
from pilot_data.models import ItemType, ItemGroup, TypeAttribute, TypeEffect, AttributeDefinition

class Command(BaseCommand):
    help = 'Imports Eve Online Static Data Export (SDE) items, groups, attributes, and effects.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting SDE Import...'))
        
        # 1. Groups
        self.import_inv_groups()
        
        # 2. Types
        self.import_inv_types()
        
        # 3. Attribute Definitions (NEW)
        self.import_dogma_attribute_definitions()
        
        # 4. Attributes (Published Only)
        self.import_dogma_attributes()

        # 5. Effects (For Slot Detection)
        self.import_dogma_effects()
        
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

    def import_dogma_attribute_definitions(self):
        """
        Imports dgmAttributeTypes.csv to populate AttributeDefinition model.
        This gives us the names ('CPU Usage', 'Shield Bonus') for the IDs.
        """
        url = "https://www.fuzzwork.co.uk/dump/latest/dgmAttributeTypes.csv"
        self.stdout.write(f"Downloading Attribute Definitions from {url}...")

        try:
            response = requests.get(url)
            response.raise_for_status()
            
            csv_content = io.StringIO(response.content.decode('utf-8'))
            df = pd.read_csv(csv_content)
            
            self.stdout.write(f"Processing {len(df)} definitions...")
            
            defs_to_create = []
            
            for row in df.itertuples():
                defs_to_create.append(
                    AttributeDefinition(
                        attribute_id=row.attributeID,
                        name=row.attributeName,
                        description=row.description if hasattr(row, 'description') and pd.notna(row.description) else "",
                        display_name=row.displayName if hasattr(row, 'displayName') and pd.notna(row.displayName) else None,
                        unit_id=row.unitID if hasattr(row, 'unitID') and pd.notna(row.unitID) else None,
                        published=bool(row.published) if hasattr(row, 'published') else True
                    )
                )
                
                if len(defs_to_create) >= 1000:
                    AttributeDefinition.objects.bulk_create(defs_to_create, ignore_conflicts=True)
                    defs_to_create = []

            if defs_to_create:
                AttributeDefinition.objects.bulk_create(defs_to_create, ignore_conflicts=True)
            
            self.stdout.write(self.style.SUCCESS("Attribute Definitions Import complete."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing Attribute Definitions: {e}"))

    def import_dogma_attributes(self):
        """
        1. Downloads dgmTypeAttributes.csv.
        2. Filters rows to only include attributes we know about (from AttributeDefinition).
        """
        val_url = "https://www.fuzzwork.co.uk/dump/latest/dgmTypeAttributes.csv"
        self.stdout.write(f"Downloading Item Attributes from {val_url}...")
        
        try:
            # 1. Get Set of Valid Attribute IDs to enforce integrity
            valid_attr_ids = set(AttributeDefinition.objects.values_list('attribute_id', flat=True))
            
            if not valid_attr_ids:
                self.stdout.write(self.style.WARNING("No Attribute Definitions found! Run Definitions import first."))
                return

            response = requests.get(val_url)
            response.raise_for_status()
            
            csv_content = io.StringIO(response.content.decode('utf-8'))
            df = pd.read_csv(csv_content)
            
            # THE FILTER: Keep only if attributeID is in our Definition table
            df_filtered = df[df['attributeID'].isin(valid_attr_ids)]
            
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

            if attrs_to_create:
                TypeAttribute.objects.bulk_create(attrs_to_create, ignore_conflicts=True)
                
            self.stdout.write(self.style.SUCCESS("\nAttribute Import complete."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing Attributes: {e}"))

    def import_dogma_effects(self):
        """
        Imports dgmTypeEffects.csv.
        Used to determine if a module is High/Mid/Low slot.
        """
        url = "https://www.fuzzwork.co.uk/dump/latest/dgmTypeEffects.csv"
        self.stdout.write(f"Downloading Type Effects from {url}...")

        try:
            response = requests.get(url)
            response.raise_for_status()
            
            csv_content = io.StringIO(response.content.decode('utf-8'))
            df = pd.read_csv(csv_content)
            
            self.stdout.write(f"Processing {len(df)} effects...")
            
            effects_to_create = []
            valid_type_ids = set(ItemType.objects.values_list('type_id', flat=True))

            for row in df.itertuples():
                if row.typeID not in valid_type_ids:
                    continue

                effects_to_create.append(
                    TypeEffect(
                        item_id=row.typeID,
                        effect_id=row.effectID,
                        is_default=bool(row.isDefault) if hasattr(row, 'isDefault') else False
                    )
                )
                
                if len(effects_to_create) >= 5000:
                    TypeEffect.objects.bulk_create(effects_to_create, ignore_conflicts=True)
                    effects_to_create = []

            if effects_to_create:
                TypeEffect.objects.bulk_create(effects_to_create, ignore_conflicts=True)
                
            self.stdout.write(self.style.SUCCESS("Effects Import complete."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing Effects: {e}"))