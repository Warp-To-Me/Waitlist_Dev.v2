from celery import shared_task
from django.utils import timezone
from core.models import Ban, BanAuditLog
from django.contrib.auth.models import User

@shared_task
def check_expired_bans():
    """
    Checks for bans that have expired and logs them in the audit log.
    """
    now = timezone.now()

    # Find bans that have expired but haven't been logged yet
    expired_bans = Ban.objects.filter(
        expires_at__lt=now,
        expiration_logged=False
    )

    count = 0
    system_user = None # Actor is None for system/automatic actions, or we can use a special user if desired.

    for ban in expired_bans:
        BanAuditLog.objects.create(
            target_user=ban.user,
            ban=ban,
            actor=None, # System action
            action='expire',
            details=f"Ban expired automatically on {ban.expires_at}"
        )
        ban.expiration_logged = True
        ban.save()
        count += 1

    return f"Processed {count} expired bans."
