from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from core.models import RolePriority
from core.utils import ROLE_HIERARCHY_DEFAULT

class Command(BaseCommand):
    help = 'Populates the RolePriority table based on the default ROLE_HIERARCHY.'

    def handle(self, *args, **options):
        self.stdout.write("Setting up Role Priorities...")

        for index, role_name in enumerate(ROLE_HIERARCHY_DEFAULT):
            group, created = Group.objects.get_or_create(name=role_name)
            
            # Create or Update priority
            rp, _ = RolePriority.objects.update_or_create(
                group=group,
                defaults={'level': index}
            )
            self.stdout.write(f" -> {role_name}: Level {index}")

        # Handle any groups NOT in the default list (assign them to bottom)
        others = Group.objects.exclude(name__in=ROLE_HIERARCHY_DEFAULT)
        start_level = len(ROLE_HIERARCHY_DEFAULT)
        for i, group in enumerate(others):
            RolePriority.objects.update_or_create(
                group=group,
                defaults={'level': start_level + i}
            )
            self.stdout.write(f" -> {group.name} (Other): Level {start_level + i}")

        self.stdout.write(self.style.SUCCESS("Done."))