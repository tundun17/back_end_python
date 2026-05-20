from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# Quản lý nhà
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


# Quản lý phòng
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


# Quản lý ESP32
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


# Quản lý công tắc/thiết bị bật tắt
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

    def __str__(self):
        return f"{self.name} ({self.switch_code})"


# Lưu dữ liệu cảm biến từ MQTT topic {hashcode}/sensor
class SensorReading(models.Model):
    device = models.ForeignKey(
        EspDevice,
        on_delete=models.CASCADE,
        related_name="sensor_readings"
    )

    temperature = models.FloatField(null=True, blank=True)
    humidity = models.FloatField(null=True, blank=True)
    smoke_level = models.FloatField(null=True, blank=True)
    is_smoke_detected = models.BooleanField(default=False)

    recorded_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["device", "recorded_at"]),
            models.Index(fields=["recorded_at"]),
            models.Index(fields=["is_smoke_detected"]),
        ]

    def __str__(self):
        return f"{self.device.hashcode} - {self.recorded_at}"


# Lưu lịch sử lệnh điều khiển Switch
class DeviceCommand(models.Model):
    class CommandType(models.TextChoices):
        SET_SWITCH_STATE = "SET_SWITCH_STATE", "Đặt trạng thái switch"

    class CommandStatus(models.TextChoices):
        PENDING = "PENDING", "Đang chờ xử lý"
        PUBLISHED = "PUBLISHED", "Đã publish MQTT"
        DONE = "DONE", "ESP đã thực hiện"
        FAILED = "FAILED", "Thất bại"
        TIMEOUT = "TIMEOUT", "Quá thời gian phản hồi"

    device = models.ForeignKey(
        EspDevice,
        on_delete=models.CASCADE,
        related_name="commands"
    )
    switch = models.ForeignKey(
        Switch,
        on_delete=models.CASCADE,
        related_name="commands"
    )

    command_type = models.CharField(
        max_length=50,
        choices=CommandType.choices,
        default=CommandType.SET_SWITCH_STATE
    )
    command_value = models.CharField(
        max_length=10,
        choices=Switch.State.choices
    )

    mqtt_topic = models.CharField(max_length=150, blank=True)
    mqtt_payload = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=20,
        choices=CommandStatus.choices,
        default=CommandStatus.PENDING
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="device_commands"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["device", "status"]),
            models.Index(fields=["switch", "status"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.switch.name} - {self.command_value} - {self.status}"


# Lưu cảnh báo hệ thống
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
        EspDevice,
        on_delete=models.CASCADE,
        related_name="alerts"
    )
    sensor_reading = models.ForeignKey(
        SensorReading,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts"
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
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["device", "is_resolved"]),
            models.Index(fields=["alert_type"]),
            models.Index(fields=["severity"]),
            models.Index(fields=["is_resolved"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.alert_type} - {self.device.hashcode}"
    
# Lưu log MQTT inbound/outbound
class MqttMessage(models.Model):
    class Direction(models.TextChoices):
        INBOUND = "INBOUND", "ESP gửi lên Django"
        OUTBOUND = "OUTBOUND", "Django gửi xuống ESP"

    class MessageType(models.TextChoices):
        PING = "PING", "Ping online"
        SENSOR = "SENSOR", "Dữ liệu cảm biến"
        STATE = "STATE", "Trạng thái switch"
        SET = "SET", "Lệnh điều khiển"
        UNKNOWN = "UNKNOWN", "Không xác định"

    device = models.ForeignKey(
        EspDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mqtt_messages"
    )

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

    payload = models.JSONField(default=dict, blank=True)

    is_processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["device", "created_at"]),
            models.Index(fields=["topic"]),
            models.Index(fields=["direction"]),
            models.Index(fields=["message_type"]),
            models.Index(fields=["is_processed"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.direction} - {self.topic} - {self.message_type}"
    
# Lưu lịch sử thao tác của user và hệ thống
class ActivityLog(models.Model):
    class Action(models.TextChoices):
        USER_ACTION = "USER_ACTION", "Thao tác người dùng"
        SWITCH_CONTROL = "SWITCH_CONTROL", "Điều khiển switch"
        DEVICE_ONLINE = "DEVICE_ONLINE", "Thiết bị online"
        DEVICE_OFFLINE = "DEVICE_OFFLINE", "Thiết bị offline"
        SENSOR_READING = "SENSOR_READING", "Nhận dữ liệu cảm biến"
        ALERT_CREATED = "ALERT_CREATED", "Tạo cảnh báo"
        ALERT_RESOLVED = "ALERT_RESOLVED", "Xử lý cảnh báo"
        MQTT_MESSAGE = "MQTT_MESSAGE", "Xử lý MQTT message"
        SYSTEM = "SYSTEM", "Hệ thống"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs"
    )

    device = models.ForeignKey(
        EspDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs"
    )

    action = models.CharField(
        max_length=50,
        choices=Action.choices
    )

    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["device", "created_at"]),
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.action} - {self.created_at}"