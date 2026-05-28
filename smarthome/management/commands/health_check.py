import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from smarthome.models import ESP


class Command(BaseCommand):
    help = "Check ESP last_seen_at and mark inactive ESP devices as OFFLINE"

    def handle(self, *args, **options):
        interval_minutes = getattr(settings, "ESP_HEALTH_CHECK_INTERVAL_MINUTES", 1)

        if interval_minutes <= 0:
            self.stderr.write(
                self.style.ERROR("ESP_HEALTH_CHECK_INTERVAL_MINUTES phai lon hon 0.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Health check loop started. Interval: {interval_minutes} minute(s)."
            )
        )

        while True:
            self.run_health_check()
            time.sleep(interval_minutes * 60)

    def run_health_check(self):
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
