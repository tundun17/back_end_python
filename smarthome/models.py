from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Home(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="homes",
    )
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)


    class Meta:
        db_table = "homes"
        ordering = ["name"]

    def __str__(self):
        return self.name


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
        db_table = "rooms"
        ordering = ["home", "floor", "name"]
        unique_together = ("home", "name")

    def __str__(self):
        return f"{self.home.name} - {self.name}"


class ESP(TimeStampedModel):
    class Status(models.TextChoices):
        UNCLAIMED = "UNCLAIMED", "Chưa gán"
        ONLINE = "ONLINE", "Đang online"
        OFFLINE = "OFFLINE", "Đang offline"
        ERROR = "ERROR", "Lỗi"


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
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNCLAIMED
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "esps"
        ordering = ["hashcode"]
        indexes = [
            models.Index(fields=["hashcode"]),
            models.Index(fields=["status"]),
            models.Index(fields=["home", "status"]),
        ]

    def __str__(self):
        return f"{self.esp_name} - {self.hashcode}"


class Switch(TimeStampedModel):
    class State(models.TextChoices):
        ON = "ON", "Bật"
        OFF = "OFF", "Tắt"
        
    class SyncStatus(models.TextChoices):
        SYNCED = "SYNCED", "Đã đồng bộ"
        PENDING = "PENDING", "Đang chờ ESP xác nhận"
        FAILED = "FAILED", "Đồng bộ thất bại"

    esp_device = models.ForeignKey(
        ESP,
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
    switch_code = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
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
    last_controlled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "switches"
        ordering = ["esp_device", "switch_code"]
        unique_together = ("esp_device", "switch_code")

    def __str__(self):
        return f"{self.esp_device.hashcode} - {self.name}"


class SensorReading(models.Model):
    device = models.ForeignKey(
        ESP,
        on_delete=models.CASCADE,
        related_name="sensor_readings",
    )
    temperature = models.FloatField(null=True, blank=True)
    humidity = models.FloatField(null=True, blank=True)
    smoke_level = models.FloatField(null=True, blank=True)
    is_smoke_detected = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sensor_readings"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.device.hashcode} - {self.created_at}"


class DeviceCommand(models.Model):

    class CommandStatus(models.TextChoices):
        PENDING = "PENDING", "Đang chờ xử lý"
        PUBLISHED = "PUBLISHED", "Đã publish MQTT"
        DONE = "DONE", "ESP đã thực hiện"
        FAILED = "FAILED", "Thất bại"
        TIMEOUT = "TIMEOUT", "Quá thời gian phản hồi"



    esp = models.ForeignKey(
        ESP,
        on_delete=models.CASCADE,
        related_name="commands",
    )
    switch = models.ForeignKey(
        Switch,
        on_delete=models.SET_NULL,
        related_name="commands",
        null=True,
        blank=True,
    )
    command_type = models.CharField(max_length=50, default="SET_DEVICE_STATE")
    command_value = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20,
        choices=CommandStatus.choices,
        default=CommandStatus.PENDING
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="device_commands",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "device_commands"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.esp.hashcode} - {self.command_type} - {self.command_value}"


class Alert(models.Model):
    class AlertType(models.TextChoices):
        HIGH_TEMPERATURE = "HIGH_TEMPERATURE", "Nhiệt độ cao"
        HIGH_HUMIDITY = "HIGH_HUMIDITY", "Độ ẩm cao"
        HIGH_SMOKE_LEVEL = "HIGH_SMOKE_LEVEL", "Mức khói cao"
        SMOKE_DETECTED = "SMOKE_DETECTED", "Phát hiện khói"
        DEVICE_OFFLINE = "DEVICE_OFFLINE", "Thiết bị offline"

    class Severity(models.TextChoices):
        LOW = "LOW", "Thấp"
        MEDIUM = "MEDIUM", "Trung bình"
        HIGH = "HIGH", "Cao"
        CRITICAL = "CRITICAL", "Nghiêm trọng"

    device = models.ForeignKey(
        ESP,
        on_delete=models.CASCADE,
        related_name="alerts"
    )
    sensor_reading = models.ForeignKey(
        SensorReading,
        on_delete=models.SET_NULL,
        related_name="alerts",
        null=True,
        blank=True,
    )
    alert_type = models.CharField(
        max_length=50,
        choices=AlertType.choices
    )
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.MEDIUM
    )
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
        return f"{self.alert_type} - {self.device.hashcode}"

class MQTTMessage(models.Model):
    class Direction(models.TextChoices):
        INBOUND = "INBOUND", "ESP gửi lên Django"
        OUTBOUND = "OUTBOUND", "Django gửi xuống ESP"

    class MessageType(models.TextChoices):
        SYN = "SYN", "Ping online"
        ACK = "ACK", "Xac nhan MQTT"
        SENSOR = "SENSOR", "Dữ liệu cảm biến"
        STATE = "STATE", "Trạng thái switch"
        SET = "SET", "Lệnh điều khiển"
        UNKNOWN = "UNKNOWN", "Không xác định"

    topic = models.CharField(max_length=255)
    direction = models.CharField(
        max_length=20,
        choices=Direction.choices
    )
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.UNKNOWN
    )

    # Giai doan dau dung hashcode de tranh phu thuoc qua chat vao model ESP.
    device = models.ForeignKey(
        ESP,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mqtt_messages"
    )
    payload = models.JSONField(default=dict, blank=True)
    is_processed = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mqtt_messages"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.direction} - {self.topic} - {self.message_type}"

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
        return f"{self.action} - {self.created_at}"
