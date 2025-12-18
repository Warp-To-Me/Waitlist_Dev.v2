from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from core.models import Capability
from core.utils import SYSTEM_CAPABILITIES

class Command(BaseCommand):
    help = 'Syncs SYSTEM_CAPABILITIES from utils.py to DB. Removes obsolete capabilities.'

    def handle(self, *args, **options):
        self.stdout.write("Syncing Capabilities...")

        created_count = 0
        updated_count = 0
        
        # 1. Collect all defined slugs from code
        defined_slugs = set()

        for cap_data in SYSTEM_CAPABILITIES:
            # Use the explicit slug defined in utils.py
            slug = cap_data.get('slug')
            if not slug:
                self.stdout.write(self.style.ERROR(f"Capability '{cap_data['name']}' missing slug! Skipping."))
                continue
            
            defined_slugs.add(slug)

            # Update or Create
            capability, created = Capability.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': cap_data['name'],
                    'description': cap_data['desc'],
                    'category': cap_data['category']
                }
            )

            # Assign Groups (Only if created to avoid overwriting custom manual assignments, 
            # OR we can enforce it. Let's enforce it for consistency.)
            # Actually, typically we want to ADD missing defaults but not remove custom ones.
            if 'roles' in cap_data:
                for role_name in cap_data['roles']:
                    try:
                        group = Group.objects.get(name=role_name)
                        # Only add if not present
                        if not capability.groups.filter(id=group.id).exists():
                            capability.groups.add(group)
                    except Group.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Role '{role_name}' not found for '{slug}'"))

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"+ Created: {slug}"))
            else:
                updated_count += 1
                # self.stdout.write(f". Verified: {slug}")

        # 2. Cleanup: Delete capabilities in DB that are NOT in the defined list
        # This removes duplicates and deprecated permissions
        deleted_count, _ = Capability.objects.exclude(slug__in=defined_slugs).delete()
        
        if deleted_count > 0:
            self.stdout.write(self.style.WARNING(f"- Deleted {deleted_count} obsolete capabilities."))

        self.stdout.write(self.style.SUCCESS(f"Migration Complete. Created {created_count}, Verified {updated_count}."))