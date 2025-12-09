import re
from pilot_data.models import ItemType

class EFTParser:
    """
    Parses EVE Fitting Tool (EFT) format blocks.
    Handles variations in slot ordering and spacing.
    """

    def __init__(self, eft_text):
        self.raw_text = eft_text.strip()
        self.lines = [l.strip() for l in self.raw_text.splitlines() if l.strip()]
        self.hull_name = None
        self.fit_name = None
        self.items = [] # List of dicts: {'name': str, 'quantity': int, 'item_type': ItemType obj}
        self.error = None
        self.hull_obj = None

    def parse(self):
        if not self.lines:
            self.error = "Empty EFT block."
            return False

        # 1. Parse Header: [Hull Name, Fit Name]
        header_line = self.lines[0]
        match = re.match(r'^\[(.*?), (.*?)\]$', header_line)
        
        if not match:
            self.error = "Invalid Header. Must be: [Hull Name, Fit Name]"
            return False

        self.hull_name = match.group(1).strip()
        self.fit_name = match.group(2).strip()

        # 2. Verify Hull exists in DB
        try:
            # Try exact match first
            self.hull_obj = ItemType.objects.filter(type_name__iexact=self.hull_name).first()
            if not self.hull_obj:
                self.error = f"Hull '{self.hull_name}' not found in SDE database."
                return False
        except Exception as e:
            self.error = f"Database Error looking up hull: {e}"
            return False

        # 3. Parse Modules
        # We skip the first line (header)
        for line in self.lines[1:]:
            # Skip empty slot markers often found in EFT
            if "empty" in line.lower() and "slot" in line.lower():
                continue
            if line.startswith("[") and line.endswith("]"):
                # This catches the [Empty High slot] style markers too
                continue

            # Handle Quantity: "Warrior II x5" or "Warrior II"
            qty = 1
            item_name = line
            
            # Check for xQuantity at end
            qty_match = re.search(r'\s+x(\d+)$', line)
            if qty_match:
                qty = int(qty_match.group(1))
                item_name = line[:qty_match.start()].strip()

            # FIX: Handle loaded charges (e.g. "Neutron Blaster Cannon II, Void L")
            # We split by comma and take the first part as the module name
            if ',' in item_name:
                item_name = item_name.split(',')[0].strip()

            # Lookup Item
            item_obj = ItemType.objects.filter(type_name__iexact=item_name).first()
            
            if item_obj:
                self.items.append({
                    'name': item_name,
                    'quantity': qty,
                    'obj': item_obj
                })
            else:
                # If item not found, we currently ignore it or could flag a warning.
                print(f"Warning: Item '{item_name}' not found in SDE.")

        return True