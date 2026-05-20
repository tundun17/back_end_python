from django.conf import settings
from django.db import models


class Home(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="homes",
    )
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "homes"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Room(models.Model):
    home = models.ForeignKey(Home, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=100)
    floor = models.IntegerField(default=1)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rooms"
        ordering = ["home", "floor", "name"]
        unique_together = ("home", "name")

    def __str__(self):
        return f"{self.home.name} - {self.name}"


class ESP(models.Model):
    STATUS_CHOICES = [
        ("ONLINE", "ONLINE"),
        ("OFFLINE", "OFFLINE"),
        ("ERROR", "ERROR"),
    ]

    home = models.ForeignKey(
        Home,
        on_delete=models.CASCADE,
        related_name="esp_devices",
        null=True,
        blank=True,
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        related_name="esp_devices",
        null=True,
        blank=True,
    )
    hashcode = models.CharField(max_length=100, unique=True)
    device_code = models.CharField(max_length=100, unique=True, null=True, blank=True)
    esp_name = models.CharField(max_length=100, blank=True)
    api_key = models.CharField(max_length=128, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OFFLINE")
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "esps"
        ordering = ["hashcode"]

    def __str__(self):
        return self.esp_name or self.hashcode


class Device(models.Model):
    STATE_CHOICES = [
        ("ON", "ON"),
        ("OFF", "OFF"),
    ]
    SYNC_STATUS_CHOICES = [
        ("SYNCED", "SYNCED"),
        ("PENDING", "PENDING"),
        ("FAILED", "FAILED"),
    ]

    esp = models.ForeignKey(ESP, on_delete=models.CASCADE, related_name="devices")
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        related_name="devices",
        null=True,
        blank=True,
    )
    device_code = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    gpio_pin = models.IntegerField(null=True, blank=True)
    desired_state = models.CharField(max_length=10, choices=STATE_CHOICES, default="OFF")
    actual_state = models.CharField(max_length=10, choices=STATE_CHOICES, default="OFF")
    sync_status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default="SYNCED",
    )
    last_controlled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devices"
        ordering = ["esp", "device_code"]
        unique_together = ("esp", "device_code")

    def __str__(self):
        return f"{self.esp.hashcode} - {self.name}"


class SensorReading(models.Model):
    device = models.ForeignKey(
        ESP,
        on_delete=models.CASCADE,
        related_name="sensor_readings",
    )
    temperature = models.FloatField(default=0)
    humidity = models.FloatField(default=0)
    smoke_level = models.FloatField(default=0)
    is_smoke_detected = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sensor_readings"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.device.hashcode} sensor at {self.created_at}"


class DeviceCommand(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "PENDING"),
        ("SENT", "SENT"),
        ("DONE", "DONE"),
        ("FAILED", "FAILED"),
        ("EXPIRED", "EXPIRED"),
    ]

    device = models.ForeignKey(
        ESP,
        on_delete=models.CASCADE,
        related_name="commands",
    )
    controlled_device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        related_name="commands",
        null=True,
        blank=True,
    )
    command_type = models.CharField(max_length=50, default="SET_DEVICE_STATE")
    command_value = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="device_commands",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "device_commands"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.device.hashcode} {self.command_type} {self.command_value}"


class Alert(models.Model):
    SEVERITY_CHOICES = [
        ("LOW", "LOW"),
        ("MEDIUM", "MEDIUM"),
        ("HIGH", "HIGH"),
        ("CRITICAL", "CRITICAL"),
    ]

    device = models.ForeignKey(ESP, on_delete=models.CASCADE, related_name="alerts")
    sensor_reading = models.ForeignKey(
        SensorReading,
        on_delete=models.SET_NULL,
        related_name="alerts",
        null=True,
        blank=True,
    )
    alert_type = models.CharField(max_length=50)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    message = models.TextField()
    threshold_value = models.FloatField(null=True, blank=True)
    actual_value = models.FloatField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "alerts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.alert_type} - {self.severity}"


class ActivityLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
        null=True,
        blank=True,
    )
    device = models.ForeignKey(
        ESP,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "activity_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return self.action
