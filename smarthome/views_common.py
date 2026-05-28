from django.http import HttpResponse
from django.utils import timezone


def index(request):
    return HttpResponse("Xin chao. <br>Ban da den trang Smart Home Backend")


def missing_fields(body, required_fields):
    return [field for field in required_fields if field not in body]


def parse_boolean(value, default=False):
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value = value.strip().lower()
        if value in ["true", "1", "yes"]:
            return True
        if value in ["false", "0", "no"]:
            return False

    return default


def user_to_dict(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_joined": user.date_joined,
    }


def home_to_dict(home):
    return {
        "id": home.id,
        "name": home.name,
        "address": home.address,
        "description": home.description,
        "created_at": home.created_at,
        "updated_at": home.updated_at,
    }


def room_to_dict(room):
    return {
        "id": room.id,
        "home_id": room.home_id,
        "home_name": room.home.name,
        "name": room.name,
        "floor": room.floor,
        "description": room.description,
        "created_at": room.created_at,
        "updated_at": room.updated_at,
    }


def home_overview_to_dict(home):
    from .models import Alert, ESP, Room, Switch

    rooms = Room.objects.filter(home=home)
    esps = ESP.objects.filter(home=home)
    switches = Switch.objects.filter(esp_device__home=home)
    alerts = Alert.objects.filter(device__home=home)
    active_alerts = alerts.filter(is_resolved=False)

    return {
        "home": home_to_dict(home),
        "summary": {
            "total_rooms": rooms.count(),
            "total_esps": esps.count(),
            "online_esps": esps.filter(status=ESP.Status.ONLINE).count(),
            "offline_esps": esps.filter(status=ESP.Status.OFFLINE).count(),
            "total_switches": switches.count(),
            "switches_on": switches.filter(actual_state=Switch.State.ON).count(),
            "switches_off": switches.filter(actual_state=Switch.State.OFF).count(),
            "active_alerts": active_alerts.count(),
            "resolved_alerts": alerts.filter(is_resolved=True).count(),
        },
        "esp_status": {
            "unclaimed": esps.filter(status=ESP.Status.UNCLAIMED).count(),
            "online": esps.filter(status=ESP.Status.ONLINE).count(),
            "offline": esps.filter(status=ESP.Status.OFFLINE).count(),
            "error": esps.filter(status=ESP.Status.ERROR).count(),
            "sensor_esps": esps.filter(is_sensor=True).count(),
            "control_esps": esps.filter(is_sensor=False).count(),
        },
        "switch_sync": {
            "synced": switches.filter(sync_status=Switch.SyncStatus.SYNCED).count(),
            "pending": switches.filter(sync_status=Switch.SyncStatus.PENDING).count(),
            "failed": switches.filter(sync_status=Switch.SyncStatus.FAILED).count(),
        },
        "alert_status": {
            "low": active_alerts.filter(severity=Alert.Severity.LOW).count(),
            "medium": active_alerts.filter(severity=Alert.Severity.MEDIUM).count(),
            "high": active_alerts.filter(severity=Alert.Severity.HIGH).count(),
            "critical": active_alerts.filter(severity=Alert.Severity.CRITICAL).count(),
        },
        "updated_at": timezone.now(),
    }


def esp_to_dict(esp):
    return {
        "id": esp.id,
        "home_id": esp.home_id,
        "room_id": esp.room_id,
        "hashcode": esp.hashcode,
        "name": esp.esp_name,
        "is_sensor": esp.is_sensor,
        "status": esp.status,
        "ip_address": esp.ip_address,
        "firmware_version": esp.firmware_version,
        "last_seen_at": esp.last_seen_at,
        "created_at": esp.created_at,
        "updated_at": esp.updated_at,
    }


def switch_to_dict(switch):
    return {
        "id": switch.id,
        "esp_id": switch.esp_device_id,
        "hashcode": switch.esp_device.hashcode,
        "switch_code": switch.switch_code,
        "switch_name": switch.switch_name,
        "desired_state": switch.desired_state,
        "actual_state": switch.actual_state,
        "sync_status": switch.sync_status,
        "last_controlled_at": switch.last_controlled_at,
        "created_at": switch.created_at,
        "updated_at": switch.updated_at,
    }


def command_to_dict(command):
    return {
        "id": command.id,
        "esp_id": command.esp_id,
        "hashcode": command.esp.hashcode,
        "switch_id": command.switch_id,
        "switch_code": command.switch.switch_code if command.switch else None,
        "command_type": command.command_type,
        "command_value": command.command_value,
        "status": command.status,
        "created_by_id": command.created_by_id,
        "created_at": command.created_at,
        "published_at": command.published_at,
        "acknowledged_at": command.acknowledged_at,
        "error_message": command.error_message,
    }


def mqtt_message_to_dict(message):
    return {
        "id": message.id,
        "device_id": message.device_id,
        "hashcode": message.device.hashcode if message.device else None,
        "topic": message.topic,
        "direction": message.direction,
        "message_type": message.message_type,
        "payload": message.payload,
        "is_processed": message.is_processed,
        "error_message": message.error_message,
        "created_at": message.created_at,
    }


def sensor_reading_to_dict(reading):
    return {
        "id": reading.id,
        "device_id": reading.device_id,
        "hashcode": reading.device.hashcode,
        "temperature": reading.temperature,
        "humidity": reading.humidity,
        "gas": reading.gas,
        "recorded_at": reading.recorded_at,
        "created_at": reading.created_at,
    }


def alert_to_dict(alert):
    return {
        "id": alert.id,
        "device_id": alert.device_id,
        "hashcode": alert.device.hashcode,
        "sensor_reading_id": alert.sensor_reading_id,
        "alert_type": alert.alert_type,
        "alert_type_display": alert.get_alert_type_display(),
        "severity": alert.severity,
        "severity_display": alert.get_severity_display(),
        "message": alert.message,
        "threshold_value": alert.threshold_value,
        "actual_value": alert.actual_value,
        "is_resolved": alert.is_resolved,
        "created_at": alert.created_at,
        "resolved_at": alert.resolved_at,
    }


def automation_rule_to_dict(rule):
    return {
        "id": rule.id,
        "sensor_esp_id": rule.sensor_device_id,
        "sensor_hashcode": rule.sensor_device.hashcode,
        "target_switch_id": rule.target_switch_id,
        "target_hashcode": rule.target_switch.esp_device.hashcode,
        "switch_code": rule.target_switch.switch_code,
        "switch_name": rule.target_switch.switch_name,
        "alert_type": rule.alert_type,
        "alert_type_display": rule.get_alert_type_display(),
        "enabled": rule.enabled,
        "active_state": rule.active_state,
        "normal_state": rule.normal_state,
        "last_triggered_at": rule.last_triggered_at,
        "last_normalized_at": rule.last_normalized_at,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }
