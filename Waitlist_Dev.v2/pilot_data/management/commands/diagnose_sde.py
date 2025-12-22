from django.core.management.base import BaseCommand
from pilot_data.models import ItemType, TypeEffect
from waitlist_data.views.helpers import _determine_slot
from core.eft_parser import EFTParser

TEST_BLOCK = """[Vargur, Vargur Standard]
Auto Targeting System I
800mm Repeating Cannon II
800mm Repeating Cannon II
800mm Repeating Cannon II
800mm Repeating Cannon II
Bastion Module I

Pithum B-Type Multispectrum Shield Hardener
Pithum B-Type Multispectrum Shield Hardener
Large Micro Jump Drive
Federation Navy Tracking Computer
Pith X-Type X-Large Shield Booster
Gist X-Type 500MN Microwarpdrive

Domination Tracking Enhancer
Domination Tracking Enhancer
Republic Fleet Gyrostabilizer
Republic Fleet Gyrostabilizer
Republic Fleet Gyrostabilizer
Republic Fleet Gyrostabilizer

Large Projectile Ambit Extension I
Large Projectile Burst Aerator II


Federation Navy Hammerhead x5

Barrage L x1
Hail L x1
Federation Navy Tracking Computer x1
Nanite Repair Paste x50
Synth Sooth Sayer Booster x1
Optimal Range Script x1
Tracking Speed Script x1
Agency 'Pyrolancea' DB3 Dose I x1
Agency 'Pyrolancea' DB7 Dose III x1
"""

class Command(BaseCommand):
    help = 'Diagnoses SDE data for a specific item to understand slot determination failures.'

    def add_arguments(self, parser):
        parser.add_argument(
            'item_name',
            nargs='?',
            default='800mm Repeating Cannon II',
            help='Name of the item to diagnose'
        )
        parser.add_argument(
            '--test-block',
            action='store_true',
            help='Run full EFT Parser test with the provided block'
        )

    def handle(self, *args, **options):
        if options['test_block']:
            self.run_parser_test()
            return

        item_name = options['item_name']
        self.diagnose_item(item_name)

    def diagnose_item(self, item_name):
        self.stdout.write(f"Diagnosing Item: '{item_name}'")

        # 1. Lookup Item
        item = ItemType.objects.filter(type_name__iexact=item_name).first()
        if not item:
            item = ItemType.objects.filter(type_name__icontains=item_name).first()
            if item:
                self.stdout.write(self.style.WARNING(f"Exact match not found. Found partial match: '{item.type_name}'"))
            else:
                self.stdout.write(self.style.ERROR(f"Item '{item_name}' not found in database."))
                return

        self.stdout.write(f"Found Item: {item.type_name} (ID: {item.type_id})")

        # 2. Group Info
        if item.group:
            self.stdout.write(f"Group: {item.group.group_name} (ID: {item.group.group_id})")
            self.stdout.write(f"Category ID: {item.group.category_id}")
        else:
            self.stdout.write(self.style.ERROR("Item has NO Group assigned!"))

        # 3. Effects
        effects = TypeEffect.objects.filter(item=item)
        count = effects.count()
        self.stdout.write(f"TypeEffects Found: {count}")

        effect_ids = set()
        for effect in effects:
            is_default_str = " (Default)" if effect.is_default else ""
            self.stdout.write(f" - Effect ID: {effect.effect_id}{is_default_str}")
            effect_ids.add(effect.effect_id)

        if 12 in effect_ids: self.stdout.write(self.style.SUCCESS(" -> Has High Slot Effect (12)"))
        elif 13 in effect_ids: self.stdout.write(self.style.SUCCESS(" -> Has Mid Slot Effect (13)"))
        elif 11 in effect_ids: self.stdout.write(self.style.SUCCESS(" -> Has Low Slot Effect (11)"))
        elif 2663 in effect_ids: self.stdout.write(self.style.SUCCESS(" -> Has Rig Slot Effect (2663)"))

        # 4. Test Function
        self.stdout.write("Testing _determine_slot() function...")
        try:
            slot = _determine_slot(item)
            self.stdout.write(f"Result: '{slot}'")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Function raised exception: {e}"))

    def run_parser_test(self):
        self.stdout.write("Running EFT Parser Test...")
        parser = EFTParser(TEST_BLOCK)
        if not parser.parse():
            self.stdout.write(self.style.ERROR(f"Parser failed: {parser.error}"))
            return

        self.stdout.write(f"Hull: {parser.hull_name} (Obj: {parser.hull_obj})")
        self.stdout.write(f"Fit Name: {parser.fit_name}")
        self.stdout.write(f"Items Found: {len(parser.items)}")

        for i, item in enumerate(parser.items):
            obj = item['obj']
            slot = _determine_slot(obj)
            group_str = f"Group: {obj.group.group_id} ({obj.group.group_name})" if obj.group else "No Group"
            self.stdout.write(f"[{i+1}] {item['name']} -> ID: {obj.type_id} -> {group_str} -> Slot: {slot}")

            if item['name'] == '800mm Repeating Cannon II' and slot == 'cargo':
                 self.stdout.write(self.style.ERROR("   ^^ FAILED: Should be High Slot!"))
                 # Run deep diagnosis for this failure
                 self.diagnose_item(item['name'])
