import os
import django
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'waitlist_project.settings')
django.setup()

from django.contrib.auth.models import User, Group
from django.contrib.sessions.backends.db import SessionStore
from core.models import Ban, Capability
from pilot_data.models import EveCharacter

def setup_management_session():
    username = "mgmt_user"
    user, _ = User.objects.get_or_create(username=username)
    user.is_staff = True # Needed for some checks? Or just capabilities.
    user.save()

    # Ensure character
    EveCharacter.objects.get_or_create(
        character_id=99001,
        defaults={'character_name': 'Mgmt Pilot', 'user': user, 'is_main': True}
    )

    # Add 'can_manage_bans' capability
    cap, _ = Capability.objects.get_or_create(slug='can_manage_bans', defaults={'name': 'Manage Bans'})
    group, _ = Group.objects.get_or_create(name='Management')
    cap.groups.add(group)
    user.groups.add(group)

    # Create Bans
    # 1. Active (Future Expiry)
    target1, _ = User.objects.get_or_create(username="banned_active")
    EveCharacter.objects.get_or_create(character_id=99002, defaults={'character_name': 'Active Ban Target', 'user': target1, 'is_main': True})
    Ban.objects.filter(user=target1).delete()
    Ban.objects.create(user=target1, reason="Active Ban", expires_at=timezone.now() + timedelta(days=1), issuer=user)

    # 2. Permanent
    target2, _ = User.objects.get_or_create(username="banned_perm")
    EveCharacter.objects.get_or_create(character_id=99003, defaults={'character_name': 'Perm Ban Target', 'user': target2, 'is_main': True})
    Ban.objects.filter(user=target2).delete()
    Ban.objects.create(user=target2, reason="Perm Ban", expires_at=None, issuer=user)

    # 3. Expired
    target3, _ = User.objects.get_or_create(username="banned_expired")
    EveCharacter.objects.get_or_create(character_id=99004, defaults={'character_name': 'Expired Ban Target', 'user': target3, 'is_main': True})
    Ban.objects.filter(user=target3).delete()
    # Create an expired ban manually (bypass manager?)
    b = Ban(user=target3, reason="Expired Ban", expires_at=timezone.now() - timedelta(days=1), issuer=user)
    b.save()

    # Create session
    session = SessionStore()
    session['_auth_user_id'] = user.id.hex if hasattr(user.id, 'hex') else str(user.id)
    session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
    session['_auth_user_hash'] = user.get_session_auth_hash()
    session.save()

    print(session.session_key)

if __name__ == "__main__":
    setup_management_session()
