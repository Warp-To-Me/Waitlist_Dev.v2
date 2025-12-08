from django.core.management.base import BaseCommand
import pandas as pd
import requests
import io
from django.db import transaction
from pilot_data.models import ItemType, ItemGroup, TypeAttribute, TypeEffect, AttributeDefinition

class Command(BaseCommand):
    help = 'Imports Eve Online Static Data Export (SDE) items, groups, attributes, and effects.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Wipe existing SDE data before importing (Recommended for schema changes)',
        )

    def handle(self, *args, **options):
        if options['clean']:
            self.stdout.write(self.style.WARNING('Wiping existing SDE data...'))
            # Order matters due to ForeignKeys
            TypeAttribute.objects.all().delete()
            TypeEffect.objects.all().delete()
            ItemType.objects.all().delete()
            # We don't delete AttributeDefinition or ItemGroup unless necessary, 
            # but for a full clean, we should.
            # However, FitAnalysisRule depends on AttributeDefinition/ItemGroup.
            # Wiping them might cascade delete your Rules. 
            # SAFE WIPE: Only wipe Items and their children. Groups usually don't change IDs.
            self.stdout.write(self.style.SUCCESS('Items and Attributes wiped. Groups preserved to protect Rules.'))

        self.stdout.write(self.style.SUCCESS('Starting SDE Import...'))
        
        # 1. Groups (Update or Create to be safe)
        self.import_inv_groups()
        
        # 2. Attribute Definitions (Update or Create)
        self.import_dogma_attribute_definitions()
        
        # 3. Types (This will re-populate the wiped table)
        self.import_inv_types()
        
        # 4. Attributes (Published Only)
        self.import_dogma_attributes()

        # 5. Effects (For Slot Detection)
        self.import_dogma_effects()
        
        self.stdout.write(self.style.SUCCESS('Full SDE Import Complete.'))

    def import_inv_groups(self):
        url = "https://www.fuzzwork.co.uk/dump/latest/invGroups.csv"
        self.stdout.write(f"Downloading Groups from {url}...")
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            
            self.stdout.write(f"Processing {len(df)} groups...")
            groups_to_create = []
            existing_ids = set(ItemGroup.objects.values_list('group_id', flat=True))
            
            for row in df.itertuples():
                # Safety check for published attribute
                published = bool(row.published) if hasattr(row, 'published') else True
                
                if row.groupID in existing_ids:
                    # Skip existing to save time, or update if we wanted to be thorough
                    continue

                groups_to_create.append(
                    ItemGroup(
                        group_id=row.groupID,
                        category_id=row.categoryID,
                        group_name=row.groupName,
                        published=published
                    )
                )
                if len(groups_to_create) >= 1000:
                    ItemGroup.objects.bulk_create(groups_to_create)
                    groups_to_create = []
            
            if groups_to_create:
                ItemGroup.objects.bulk_create(groups_to_create)
                
            self.stdout.write(self.style.SUCCESS("Group Import complete."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing Groups: {e}"))

    def import_inv_types(self):
        url = "https://www.fuzzwork.co.uk/dump/latest/invTypes.csv"
        self.stdout.write(f"Downloading Items from {url}...")
        try:
            response = requests.get(url)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            
            self.stdout.write(f"Processing {len(df)} records...")
            
            items_to_create = []
            # We filter out items that belong to groups we don't have (integrity check)
            valid_group_ids = set(ItemGroup.objects.values_list('group_id', flat=True))
            
            for row in df.itertuples():
                if row.groupID not in valid_group_ids:
                    continue

                items_to_create.append(
                    ItemType(
                        type_id=row.typeID,
                        group_id=row.groupID, # Maps to 'group' FK via db_column='group_id'
                        type_name=row.typeName,
                        description=row.description if hasattr(row, 'description') and pd.notna(row.description) else "",
                        mass=row.mass if hasattr(row, 'mass') else 0,
                        volume=row.volume if hasattr(row, 'volume') else 0,
                        capacity=row.capacity if hasattr(row, 'capacity') else 0,
                        published=bool(row.published) if hasattr(row, 'published') else True,
                        market_group_id=row.marketGroupID if hasattr(row, 'marketGroupID') and pd.notna(row.marketGroupID) else None
                    )
                )
                
                if len(items_to_create) >= 2000:
                    # Using ignore_conflicts=True is fine now because we wiped the table first
                    ItemType.objects.bulk_create(items_to_create, ignore_conflicts=True)
                    items_to_create = []
            
            if items_to_create:
                ItemType.objects.bulk_create(items_to_create, ignore_conflicts=True)
                
            self.stdout.write(self.style.SUCCESS("Item Import complete."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing SDE: {e}"))

    def import_dogma_attribute_definitions(self):
        url = "https://www.fuzzwork.co.uk/dump/latest/dgmAttributeTypes.csv"
        self.stdout.write(f"Downloading Attribute Definitions from {url}...")

        try:
            response = requests.get(url)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            
            self.stdout.write(f"Processing {len(df)} definitions...")
            defs_to_create = []
            existing_ids = set(AttributeDefinition.objects.values_list('attribute_id', flat=True))
            
            for row in df.itertuples():
                if row.attributeID in existing_ids: continue

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
                    AttributeDefinition.objects.bulk_create(defs_to_create)
                    defs_to_create = []

            if defs_to_create:
                AttributeDefinition.objects.bulk_create(defs_to_create)
            
            self.stdout.write(self.style.SUCCESS("Attribute Definitions Import complete."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing Attribute Definitions: {e}"))

    def import_dogma_attributes(self):
        val_url = "https://www.fuzzwork.co.uk/dump/latest/dgmTypeAttributes.csv"
        self.stdout.write(f"Downloading Item Attributes from {val_url}...")
        
        try:
            valid_attr_ids = set(AttributeDefinition.objects.values_list('attribute_id', flat=True))
            if not valid_attr_ids:
                self.stdout.write(self.style.WARNING("No Attribute Definitions found! Run Definitions import first."))
                return

            response = requests.get(val_url)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            df_filtered = df[df['attributeID'].isin(valid_attr_ids)]
            
            self.stdout.write(f"Processing {len(df_filtered)} attributes (Filtered from {len(df)})...")
            
            attrs_to_create = []
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
                
            self.stdout.write(self.style.SUCCESS("Attribute Import complete."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing Attributes: {e}"))

    def import_dogma_effects(self):
        url = "https://www.fuzzwork.co.uk/dump/latest/dgmTypeEffects.csv"
        self.stdout.write(f"Downloading Type Effects from {url}...")

        try:
            response = requests.get(url)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            
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