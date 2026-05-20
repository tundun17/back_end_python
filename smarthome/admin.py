from django.contrib import admin

from .models import (
    ActivityLog,
    Alert,
    Device,
    DeviceCommand,
    ESP,
    Home,
    Room,
    SensorReading,
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
    search_fields = ("hashcode", "device_code", "esp_name")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "device_code",
        "name",
        "esp",
        "desired_state",
        "actual_state",
        "sync_status",
    )
    list_filter = ("desired_state", "actual_state", "sync_status")
    search_fields = ("device_code", "name", "esp__hashcode")


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "device",
        "temperature",
        "humidity",
        "smoke_level",
        "is_smoke_detected",
        "created_at",
    )
    list_filter = ("is_smoke_detected",)
    search_fields = ("device__hashcode",)


@admin.register(DeviceCommand)
class DeviceCommandAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "device",
        "controlled_device",
        "command_value",
        "status",
        "created_at",
    )
    list_filter = ("status", "command_type")
    search_fields = ("device__hashcode", "controlled_device__device_code", "command_value")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("id", "device", "alert_type", "severity", "is_resolved", "created_at")
    list_filter = ("severity", "alert_type", "is_resolved")
    search_fields = ("device__hashcode", "message")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device", "action", "created_at")
    search_fields = ("user__username", "device__hashcode", "action", "description")
