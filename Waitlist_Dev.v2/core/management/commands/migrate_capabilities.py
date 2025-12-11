from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.utils.text import slugify
from core.models import Capability
from core.utils import SYSTEM_CAPABILITIES

class Command(BaseCommand):
    help = 'Imports hardcoded SYSTEM_CAPABILITIES from utils.py into the Capability database model and cleans up duplicates.'

    def handle(self, *args, **options):
        self.stdout.write("Migrating Capabilities...")

        created_count = 0
        updated_count = 0
        merged_count = 0

        # --- FIX: Correct legacy slug if it exists to preserve permissions ---
        try:
            bad_cap = Capability.objects.filter(slug="promotedemote_users").first()
            if bad_cap:
                # Check if the target already exists to avoid UniqueViolation
                if not Capability.objects.filter(slug="promote_demote_users").exists():
                    self.stdout.write(self.style.WARNING("Fixing legacy slug: 'promotedemote_users' -> 'promote_demote_users'"))
                    bad_cap.slug = "promote_demote_users"
                    bad_cap.save()
                else:
                    self.stdout.write(self.style.WARNING("Found legacy slug 'promotedemote_users' but target 'promote_demote_users' already exists. Skipping rename."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error checking legacy slugs: {e}"))
        # ---------------------------------------------------------------------

        for cap_data in SYSTEM_CAPABILITIES:
            # Generate a slug from the name if one doesn't exist logically
            slug = slugify(cap_data['name']).replace('-', '_')
            
            # Manual Mapping to ensure slugs match what we likely want for code checks
            if "Fleet Command" in cap_data['name']: slug = "access_fleet_command"
            if "Management Access" in cap_data['name']: slug = "access_management"
            if "Full System Access" in cap_data['name']: slug = "access_admin"
            if "View Fleet Overview" in cap_data['name']: slug = "view_fleet_overview"
            if "Inspect Pilots" in cap_data['name']: slug = "inspect_pilots"
            if "Manage Doctrines" in cap_data['name']: slug = "manage_doctrines"
            if "Promote/Demote Users" in cap_data['name']: slug = "promote_demote_users"
            if "Manage Analysis Rules" in cap_data['name']: slug = "manage_analysis_rules"
            if "View Sensitive Data" in cap_data['name']: slug = "view_sensitive_data"

            # --- NEW SRP SLUGS ---
            if "Manage SRP Source" in cap_data['name']: slug = "manage_srp_source"
            if "View SRP Dashboard" in cap_data['name']: slug = "view_srp_dashboard"

            # --- BAN SLUGS (Explicitly Defined) ---
            if "Manage Bans" in cap_data['name']: slug = "manage_bans"
            if "View Ban Audit Log" in cap_data['name']: slug = "view_ban_audit_log"

            # 1. Create or Update the CORRECT capability
            capability, created = Capability.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': cap_data['name'],
                    'description': cap_data['desc'],
                    'category': cap_data['category']
                }
            )

            # 2. Assign Groups (Reset/Ensure defaults)
            if 'roles' in cap_data:
                for role_name in cap_data['roles']:
                    try:
                        group = Group.objects.get(name=role_name)
                        capability.groups.add(group)
                    except Group.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Role '{role_name}' not found for capability '{slug}'"))

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"+ Created: {slug}"))
            else:
                updated_count += 1
                self.stdout.write(f". Verified: {slug}")

            # 3. CLEANUP: Check for legacy hyphenated duplicate (e.g., manage-bans vs manage_bans)
            # This happens because slugify defaults to hyphens, but we want underscores.
            legacy_slug = slug.replace('_', '-')
            if legacy_slug != slug:
                try:
                    legacy_cap = Capability.objects.get(slug=legacy_slug)
                    
                    # Merge groups from legacy to new
                    for grp in legacy_cap.groups.all():
                        capability.groups.add(grp)
                    
                    # Delete the duplicate
                    legacy_cap.delete()
                    merged_count += 1
                    self.stdout.write(self.style.WARNING(f"   -> Merged & Deleted duplicate slug: '{legacy_slug}'"))
                except Capability.DoesNotExist:
                    pass

        self.stdout.write(self.style.SUCCESS(f"Migration Complete. Created {created_count}, Verified {updated_count}, Merged {merged_count} Duplicates."))