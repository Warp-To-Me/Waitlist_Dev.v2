import pandas as pd
import requests
import io
# The models are in the 'pilot_data' app, NOT locally in 'esi_calls'
from pilot_data.models import ItemType, ItemGroup

def import_inv_groups():
    """
    Downloads invGroups.csv from Fuzzworks and imports it.
    """
    url = "https://www.fuzzwork.co.uk/dump/latest/invGroups.csv"
    print(f"Downloading Groups from {url}...")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        csv_content = io.StringIO(response.content.decode('utf-8'))
        df = pd.read_csv(csv_content)
        
        print(f"Processing {len(df)} groups...")
        groups_to_create = []
        
        for row in df.itertuples():
            groups_to_create.append(
                ItemGroup(
                    group_id=row.groupID,
                    category_id=row.categoryID,
                    group_name=row.groupName,
                    published=bool(row.published) if hasattr(row, 'published') else True
                )
            )
            if len(groups_to_create) >= 1000:
                ItemGroup.objects.bulk_create(groups_to_create, ignore_conflicts=True)
                groups_to_create = []
        
        if groups_to_create:
            ItemGroup.objects.bulk_create(groups_to_create, ignore_conflicts=True)
            
        print("Group Import complete.")
    except Exception as e:
        print(f"Error importing Groups: {e}")

def import_inv_types():
    """
    Downloads invTypes.csv.bz2 (or .csv) from Fuzzworks and imports it.
    """
    url = "https://www.fuzzwork.co.uk/dump/latest/invTypes.csv"
    
    print(f"Downloading Items from {url}...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        # Read CSV content
        csv_content = io.StringIO(response.content.decode('utf-8'))
        
        # Load into Pandas DataFrame
        df = pd.read_csv(csv_content)
        
        print(f"Processing {len(df)} records...")
        
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
            
        print("Item Import complete.")
        
    except Exception as e:
        print(f"Error importing SDE: {e}")

def run_full_import():
    """Helper to run both"""
    import_inv_groups()
    import_inv_types()