from django.contrib import admin
from .models import Home, Room, EspDevice, Switch, SensorReading, DeviceCommand, Alert, MqttMessage, ActivityLog


@admin.register(Home)
class HomeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "address", "created_at", "updated_at")
    search_fields = ("name", "address", "description")
    list_filter = ("created_at",)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "home", "floor", "created_at", "updated_at")
    search_fields = ("name", "description", "home__name")
    list_filter = ("home", "floor", "created_at")

@admin.register(EspDevice)
class EspDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "device_name",
        "hashcode",
        "home",
        "room",
        "status",
        "ip_address",
        "firmware_version",
        "last_seen_at",
    )
    search_fields = (
        "device_name",
        "hashcode",
        "ip_address",
        "firmware_version",
    )
    list_filter = ("status", "home", "room", "created_at")
    readonly_fields = (
        "mqtt_set_topic",
        "mqtt_state_topic",
        "mqtt_sensor_topic",
        "created_at",
        "updated_at",
    )

@admin.register(Switch)
class SwitchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "switch_code",
        "esp_device",
        "room",
        "gpio_pin",
        "desired_state",
        "actual_state",
        "sync_status",
        "is_active",
        "last_controlled_at",
    )
    search_fields = (
        "name",
        "switch_code",
        "esp_device__hashcode",
        "esp_device__device_name",
    )
    list_filter = (
        "desired_state",
        "actual_state",
        "sync_status",
        "is_active",
        "room",
    )

@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "device",
        "temperature",
        "humidity",
        "smoke_level",
        "is_smoke_detected",
        "recorded_at",
        "created_at",
    )
    search_fields = (
        "device__hashcode",
        "device__device_name",
    )
    list_filter = (
        "is_smoke_detected",
        "recorded_at",
        "created_at",
    )
    date_hierarchy = "recorded_at"

@admin.register(DeviceCommand)
class DeviceCommandAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "device",
        "switch",
        "command_type",
        "command_value",
        "status",
        "created_by",
        "created_at",
        "published_at",
        "acknowledged_at",
    )
    search_fields = (
        "device__hashcode",
        "device__device_name",
        "switch__name",
        "switch__switch_code",
    )
    list_filter = (
        "command_type",
        "command_value",
        "status",
        "created_at",
        "published_at",
        "acknowledged_at",
    )
    readonly_fields = (
        "mqtt_topic",
        "mqtt_payload",
        "created_at",
        "published_at",
        "acknowledged_at",
    )

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "device",
        "alert_type",
        "severity",
        "actual_value",
        "threshold_value",
        "is_resolved",
        "created_at",
        "resolved_at",
    )
    search_fields = (
        "device__hashcode",
        "device__device_name",
        "message",
    )
    list_filter = (
        "alert_type",
        "severity",
        "is_resolved",
        "created_at",
    )
    readonly_fields = (
        "created_at",
        "resolved_at",
    )

@admin.register(MqttMessage)
class MqttMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "device",
        "topic",
        "direction",
        "message_type",
        "is_processed",
        "created_at",
    )
    search_fields = (
        "topic",
        "device__hashcode",
        "device__device_name",
        "error_message",
    )
    list_filter = (
        "direction",
        "message_type",
        "is_processed",
        "created_at",
    )
    readonly_fields = (
        "created_at",
    )

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "device",
        "action",
        "ip_address",
        "created_at",
    )
    search_fields = (
        "user__username",
        "device__hashcode",
        "device__device_name",
        "description",
        "ip_address",
    )
    list_filter = (
        "action",
        "created_at",
    )
    readonly_fields = (
        "created_at",
    )