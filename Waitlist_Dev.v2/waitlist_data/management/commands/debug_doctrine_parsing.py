from django.core.management.base import BaseCommand
from pilot_data.models import ItemType, TypeEffect
from core.eft_parser import EFTParser
from waitlist_data.views.helpers import _determine_slot

class Command(BaseCommand):
    help = 'Debugs doctrine parsing and slot determination logic.'

    def handle(self, *args, **options):
        fit_text = """[Vargur, Vargur Standard]
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
Agency 'Pyrolancea' DB7 Dose III x1"""

        self.stdout.write(self.style.SUCCESS('Starting Debug Analysis...'))

        parser = EFTParser(fit_text)
        if not parser.parse():
            self.stdout.write(self.style.ERROR(f"Parser Failed: {parser.error}"))
            return

        self.stdout.write(f"Hull: {parser.hull_name} (ID: {parser.hull_obj.type_id if parser.hull_obj else 'None'})")
        self.stdout.write(f"Items Found: {len(parser.items)}")
        self.stdout.write("-" * 50)

        for item in parser.items:
            obj = item['obj']
            name = item['name']

            self.stdout.write(f"\nItem: {name} (ID: {obj.type_id})")

            # 1. Direct Effect Query
            effects = list(TypeEffect.objects.filter(item=obj).values_list('effect_id', flat=True))
            self.stdout.write(f"  -> DB Effects: {effects}")

            # 2. _determine_slot result
            slot = _determine_slot(obj)
            color = self.style.SUCCESS if slot != 'cargo' else self.style.WARNING
            self.stdout.write(color(f"  -> Determined Slot: {slot}"))

            # 3. Validation
            expected_high = 12 in effects
            expected_mid = 13 in effects
            expected_low = 11 in effects

            if expected_high and slot != 'high':
                self.stdout.write(self.style.ERROR("  !! MISMATCH: Has Effect 12 (High) but slot is " + slot))
            if expected_mid and slot != 'mid':
                self.stdout.write(self.style.ERROR("  !! MISMATCH: Has Effect 13 (Mid) but slot is " + slot))
            if expected_low and slot != 'low':
                self.stdout.write(self.style.ERROR("  !! MISMATCH: Has Effect 11 (Low) but slot is " + slot))
