from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User, Group
from core.models import Capability
from core.utils import SYSTEM_CAPABILITIES

class Command(BaseCommand):
    help = 'Sets up the project: Syncs Capabilities/Roles, Runs SDE Import, and Configures First User.'

    def handle(self, *args, **options):
        self.stdout.write("Starting Project Setup...")

        # 1. Sync Capabilities & Roles
        self.stdout.write("-> Syncing Capabilities and Roles...")

        for cap_data in SYSTEM_CAPABILITIES:
            slug = cap_data['slug']
            # Create/Update Capability
            cap, created = Capability.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': cap_data['name'],
                    'category': cap_data['category'],
                    'description': cap_data['desc']
                }
            )
            action = "Created" if created else "Updated"
            # self.stdout.write(f"   - {action} Capability: {slug}")

            # Sync Roles (Groups)
            for role_name in cap_data['roles']:
                group, _ = Group.objects.get_or_create(name=role_name)
                if not cap.groups.filter(id=group.id).exists():
                    cap.groups.add(group)
                    # self.stdout.write(f"     + Linked Role: {role_name}")

        self.stdout.write(self.style.SUCCESS("Capabilities synced successfully."))

        # 2. Run SDE Import
        self.stdout.write("-> Running SDE Import (This may take a while)...")
        try:
            call_command('sde_import')
            self.stdout.write(self.style.SUCCESS("SDE Import completed."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"SDE Import Failed: {e}"))

        # 3. Setup First User as Admin
        self.stdout.write("-> Configuring Admin User...")
        first_user = User.objects.order_by('id').first()
        if first_user:
            self.stdout.write(f"   - Found User: {first_user.username} (ID: {first_user.id})")

            # Make Superuser/Staff
            first_user.is_superuser = True
            first_user.is_staff = True
            first_user.save()
            self.stdout.write("   - Set as Superuser and Staff.")

            # Add to Admin Group
            admin_group, _ = Group.objects.get_or_create(name='Admin')
            if not first_user.groups.filter(name='Admin').exists():
                first_user.groups.add(admin_group)
                self.stdout.write("   - Added to 'Admin' group.")

            self.stdout.write(self.style.SUCCESS(f"User '{first_user.username}' is now fully configured as Admin."))
        else:
            self.stdout.write(self.style.WARNING("No users found in database. Please log in first, then run this script again."))

        self.stdout.write(self.style.SUCCESS("-----------------------------------"))
        self.stdout.write(self.style.SUCCESS("PROJECT SETUP COMPLETE"))
        self.stdout.write(self.style.SUCCESS("-----------------------------------"))
