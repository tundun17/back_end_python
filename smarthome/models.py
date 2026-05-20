# Create your models here.

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

#Quản lý nhà
class Home(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="homes"
    )
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

#Quản lý phòng
class Room(TimeStampedModel):
    home = models.ForeignKey(
        Home,
        on_delete=models.CASCADE,
        related_name="rooms"
    )
    name = models.CharField(max_length=100)
    floor = models.IntegerField(default=1)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["home__name", "floor", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["home", "name"],
                name="unique_room_name_per_home"
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.home.name}"

#Quản lý ESP
#ESP thuộc 1 Home, có thể gán vào 1 Room hoặc không
class EspDevice(TimeStampedModel):
    class Status(models.TextChoices):
        UNCLAIMED = "UNCLAIMED", "Chưa gán"
        ONLINE = "ONLINE", "Đang online"
        OFFLINE = "OFFLINE", "Đang offline"
        ERROR = "ERROR", "Lỗi"

    home = models.ForeignKey(
        Home,
        on_delete=models.CASCADE,
        related_name="esp_devices"
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="esp_devices"
    )

    hashcode = models.CharField(max_length=100, unique=True, db_index=True)
    device_name = models.CharField(max_length=100)

    device_secret = models.CharField(max_length=255, blank=True)

    mqtt_set_topic = models.CharField(max_length=150, blank=True)
    mqtt_state_topic = models.CharField(max_length=150, blank=True)
    mqtt_sensor_topic = models.CharField(max_length=150, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNCLAIMED
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["device_name"]
        indexes = [
            models.Index(fields=["hashcode"]),
            models.Index(fields=["status"]),
            models.Index(fields=["home", "status"]),
        ]

    def save(self, *args, **kwargs):
        if self.hashcode:
            self.mqtt_set_topic = f"{self.hashcode}/set"
            self.mqtt_state_topic = f"{self.hashcode}/state"
            self.mqtt_sensor_topic = f"{self.hashcode}/sensor"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.device_name} ({self.hashcode})"
    
class Switch(TimeStampedModel):
    class State(models.TextChoices):
        ON = "ON", "Bật"
        OFF = "OFF", "Tắt"

    class SyncStatus(models.TextChoices):
        SYNCED = "SYNCED", "Đã đồng bộ"
        PENDING = "PENDING", "Đang chờ ESP xác nhận"
        FAILED = "FAILED", "Đồng bộ thất bại"

    esp_device = models.ForeignKey(
        EspDevice,
        on_delete=models.CASCADE,
        related_name="switches"
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="switches"
    )

    switch_code = models.CharField(max_length=50)
    name = models.CharField(max_length=100)

    gpio_pin = models.IntegerField(null=True, blank=True)

    desired_state = models.CharField(
        max_length=10,
        choices=State.choices,
        default=State.OFF
    )
    actual_state = models.CharField(
        max_length=10,
        choices=State.choices,
        default=State.OFF
    )

    sync_status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.SYNCED
    )

    is_active = models.BooleanField(default=True)
    last_controlled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["esp_device", "switch_code"],
                name="unique_switch_code_per_esp"
            )
        ]
        indexes = [
            models.Index(fields=["esp_device", "switch_code"]),
            models.Index(fields=["sync_status"]),
            models.Index(fields=["is_active"]),
        ]

    def set_desired_state(self, state):
        self.desired_state = state
        self.sync_status = self.SyncStatus.PENDING
        self.last_controlled_at = timezone.now()
        self.save(
            update_fields=[
                "desired_state",
                "sync_status",
                "last_controlled_at",
                "updated_at",
            ]
        )

    def confirm_actual_state(self, state):
        self.actual_state = state
        self.sync_status = self.SyncStatus.SYNCED
        self.save(
            update_fields=[
                "actual_state",
                "sync_status",
                "updated_at",
            ]
        )

    def mark_sync_failed(self):
        self.sync_status = self.SyncStatus.FAILED
        self.save(update_fields=["sync_status", "updated_at"])

    def __str__(self):
        return f"{self.name} ({self.switch_code})"