from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from smarthome.models import ESP


class Command(BaseCommand):
    help = "Check ESP last_seen_at and mark inactive ESP devices as OFFLINE"

    def handle(self, *args, **options):
        timeout_minutes = getattr(settings, "ESP_OFFLINE_TIMEOUT_MINUTES", 10)
        offline_before = timezone.now() - timedelta(minutes=timeout_minutes)

        offline_esps = ESP.objects.filter(status=ESP.Status.ONLINE).filter(
            Q(last_seen_at__lt=offline_before) | Q(last_seen_at__isnull=True)
        )

        offline_count = offline_esps.update(status=ESP.Status.OFFLINE)

        self.stdout.write(
            self.style.SUCCESS(
                f"Health check done. Marked {offline_count} ESP device(s) as OFFLINE."
            )
        )
