from django.contrib import admin
from .models import Home, Room, EspDevice, Switch


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