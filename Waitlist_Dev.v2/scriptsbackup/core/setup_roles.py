from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from core.utils import ROLE_HIERARCHY

class Command(BaseCommand):
    help = 'Creates default user roles/groups based on hierarchy defined in core.utils'

    def handle(self, *args, **options):
        self.stdout.write("Checking Role Groups...")
        
        created_count = 0
        for role in ROLE_HIERARCHY:
            group, created = Group.objects.get_or_create(name=role)
            if created:
                self.stdout.write(self.style.SUCCESS(f" + Created Group: {role}"))
                created_count += 1
            else:
                self.stdout.write(f" - Exists: {role}")

        self.stdout.write(self.style.SUCCESS(f"Done. Created {created_count} new roles."))