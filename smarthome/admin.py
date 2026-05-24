from django.contrib import admin

from .models import (
    ActivityLog,
    Alert,
    DeviceCommand,
    ESP,
    Home,
    MQTTMessage,
    Room,
    SensorReading,
    Switch,
)


@admin.register(Home)
class HomeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "created_at")
    search_fields = ("name", "address", "owner__username")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "home", "floor", "created_at")
    list_filter = ("home",)
    search_fields = ("name", "home__name")


@admin.register(ESP)
class ESPAdmin(admin.ModelAdmin):
    list_display = ("id", "hashcode", "esp_name", "status", "last_seen_at")
    list_filter = ("status",)
    search_fields = ("hashcode", "esp_name")


@admin.register(Switch)
class SwitchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "switch_code",
        "esp_device",
        "desired_state",
        "actual_state",
        "sync_status",
    )
    list_filter = ("desired_state", "actual_state", "sync_status")
    search_fields = ("switch_code", "esp_device__hashcode")


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "device",
        "temperature",
        "humidity",
        "smoke_level",
        "created_at",
    )
    search_fields = ("device__hashcode",)


@admin.register(DeviceCommand)
class DeviceCommandAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "esp",
        "switch",
        "command_value",
        "status",
        "created_at",
    )
    list_filter = ("status", "command_type")
    search_fields = ("esp__hashcode", "switch__switch_code", "command_value")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("id", "device", "alert_type", "severity", "is_resolved", "created_at")
    list_filter = ("severity", "alert_type", "is_resolved")
    search_fields = ("device__hashcode", "message")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device", "action", "created_at")
    search_fields = ("user__username", "device__hashcode", "action", "description")


@admin.register(MQTTMessage)
class MQTTMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "topic", "direction", "message_type", "device", "is_processed", "created_at")
    list_filter = ("direction", "message_type", "is_processed")
    search_fields = ("topic", "device__hashcode", "error_message")
