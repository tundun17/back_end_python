from django.apps import apps
from django.conf import settings
from django.utils import timezone

from .services import (
    MQTTServiceError,
    parse_payload,
    detect_message_type,
    extract_hashcode_from_topic,
    log_mqtt_message,
)


def get_model_or_none(model_path: str):
    """
    model_path ví dụ:
    devices.ESP32
    devices.Devices
    sensors.SensorReading
    sensors.Alert
    controls.DeviceCommand
    """
    try:
        app_label, model_name = model_path.split(".")
        return apps.get_model(app_label, model_name)
    except Exception:
        return None


def get_esp_model():
    return get_model_or_none(getattr(settings, "MQTT_ESP_MODEL", "smarthome.ESP"))


def get_device_model():
    return get_model_or_none(getattr(settings, "MQTT_DEVICE_MODEL", "smarthome.Device"))


def get_sensor_reading_model():
    return get_model_or_none(
        getattr(settings, "MQTT_SENSOR_READING_MODEL", "sensors.SensorReading")
    )


def get_alert_model():
    return get_model_or_none(getattr(settings, "MQTT_ALERT_MODEL", "sensors.Alert"))


def get_command_model():
    return get_model_or_none(
        getattr(settings, "MQTT_COMMAND_MODEL", "controls.DeviceCommand")
    )


def set_field_if_exists(instance, field_name: str, value):
    if hasattr(instance, field_name):
        setattr(instance, field_name, value)


def get_esp_by_hashcode(hashcode: str):
    esp = get_esp_model()

    if esp is None:
        return None

    try:
        return esp.objects.filter(hashcode=hashcode).first()
    except Exception:
        return None


def update_esp_online(esp, data: dict | None = None):
    if esp is None:
        return

    data = data or {}

    set_field_if_exists(esp, "status", "ONLINE")
    set_field_if_exists(esp, "last_seen_at", timezone.now())

    if data.get("ip_address"):
        set_field_if_exists(esp, "ip_address", data.get("ip_address"))

    if data.get("firmware_version"):
        set_field_if_exists(esp, "firmware_version", data.get("firmware_version"))

    if data.get("device_code"):
        set_field_if_exists(esp, "device_code", data.get("device_code"))

    if data.get("esp_name"):
        set_field_if_exists(esp, "esp_name", data.get("esp_name"))

    esp.save()


def handle_inbound_message(topic: str, payload_text: str):
    """
    Hàm chính được mqtt_worker gọi khi nhận message từ MQTT Broker.
    """
    message_type = detect_message_type(topic)

    try:
        payload = parse_payload(payload_text)
        hashcode = extract_hashcode_from_topic(topic, payload)

        mqtt_log = log_mqtt_message(
            topic=topic,
            direction="INBOUND",
            message_type=message_type,
            device_hashcode=hashcode,
            payload=payload,
            is_processed=False,
        )

        if message_type == "SYN":
            handle_syn(payload)

        elif message_type == "SENSOR":
            handle_sensor(topic, payload)

        elif message_type == "STATE":
            handle_state(topic, payload)

        else:
            raise MQTTServiceError(f"Topic chưa được hỗ trợ: {topic}")

        mqtt_log.is_processed = True
        mqtt_log.save(update_fields=["is_processed"])

        return mqtt_log

    except Exception as exc:
        try:
            payload = {"raw": payload_text}
            hashcode = extract_hashcode_from_topic(topic, None)

            log_mqtt_message(
                topic=topic,
                direction="INBOUND",
                message_type=message_type,
                device_hashcode=hashcode,
                payload=payload,
                is_processed=False,
                error_message=str(exc),
            )
        except Exception:
            pass

        raise


def handle_syn(payload: dict):
    """
    Topic:
    ping

    Payload:
    {
        "hashcode": "ESP_ABC123",
        "device_code": "ESP32 phòng khách",
        "ip_address": "192.168.1.50",
        "firmware_version": "1.0.0"
    }
    """
    hashcode = payload.get("hashcode")

    if not hashcode:
        raise MQTTServiceError("Payload ping thiếu hashcode")

    device = get_esp_by_hashcode(hashcode)

    if device is None:
        raise MQTTServiceError(f"Khong tim thay ESP voi hashcode={hashcode}")

    update_esp_online(device, payload)


def handle_sensor(topic: str, payload: dict):
    """
    Topic:
    ESP_ABC123/sensor

    Payload:
    {
        "temperature": 31.5,
        "humidity": 72.0,
        "smoke_level": 420,
        "is_smoke_detected": false
    }
    """
    hashcode = extract_hashcode_from_topic(topic, payload)
    device = get_esp_by_hashcode(hashcode)

    if device is None:
        raise MQTTServiceError(f"Khong tim thay ESP voi hashcode={hashcode}")

    update_esp_online(device)

    SensorReading = get_sensor_reading_model()

    if SensorReading is None:
        return

    temperature = float(payload.get("temperature", 0))
    humidity = float(payload.get("humidity", 0))
    smoke_level = float(payload.get("smoke_level", 0))
    is_smoke_detected = bool(payload.get("is_smoke_detected", False))

    reading = SensorReading.objects.create(
        device=device,
        temperature=temperature,
        humidity=humidity,
        smoke_level=smoke_level,
        is_smoke_detected=is_smoke_detected,
    )

    create_alerts_if_needed(
        device=device,
        reading=reading,
        temperature=temperature,
        smoke_level=smoke_level,
        is_smoke_detected=is_smoke_detected,
    )


def create_alerts_if_needed(
    device,
    reading,
    temperature: float,
    smoke_level: float,
    is_smoke_detected: bool,
):
    Alert = get_alert_model()

    if Alert is None:
        return

    smoke_threshold = getattr(settings, "SMOKE_THRESHOLD", 800)
    temperature_threshold = getattr(settings, "TEMPERATURE_THRESHOLD", 45)

    if is_smoke_detected or smoke_level >= smoke_threshold:
        Alert.objects.create(
            device=device,
            sensor_reading=reading,
            alert_type="SMOKE_DETECTED",
            severity="CRITICAL",
            message="Phát hiện khói vượt ngưỡng an toàn",
            threshold_value=smoke_threshold,
            actual_value=smoke_level,
        )

    if temperature >= temperature_threshold:
        Alert.objects.create(
            device=device,
            sensor_reading=reading,
            alert_type="HIGH_TEMPERATURE",
            severity="HIGH",
            message="Nhiệt độ vượt ngưỡng an toàn",
            threshold_value=temperature_threshold,
            actual_value=temperature,
        )


def handle_state(topic: str, payload: dict):
    """
    Topic:
    ESP_ABC123/state

    Payload:
    {
        "command_id": 25,
        "device_code": "DEVICE_01",
        "actual_state": "ON",
        "success": true,
        "error_message": null
    }
    """
    hashcode = extract_hashcode_from_topic(topic, payload)
    esp = get_esp_by_hashcode(hashcode)

    if esp is None:
        raise MQTTServiceError(f"Khong tim thay ESP voi hashcode={hashcode}")

    update_esp_online(esp)

    device_code = payload.get("device_code")
    actual_state = payload.get("actual_state")
    success = bool(payload.get("success", True))
    command_id = payload.get("command_id")
    error_message = payload.get("error_message")

    if not device_code:
        raise MQTTServiceError("Payload state thiếu device_code")

    if actual_state not in ["ON", "OFF"]:
        raise MQTTServiceError("actual_state phải là ON hoặc OFF")

    Device = get_device_model()

    device = None

    if Device is not None:
        device = Device.objects.filter(esp=esp, device_code=device_code).first()

        if device is not None:
            device.actual_state = actual_state
            device.sync_status = "SYNCED" if success else "FAILED"
            device.save(update_fields=["actual_state", "sync_status"])

    Command = get_command_model()

    if Command is not None and command_id:
        command = Command.objects.filter(id=command_id).first()

        if command is not None:
            command.status = "DONE" if success else "FAILED"
            command.acknowledged_at = timezone.now()

            if hasattr(command, "error_message"):
                command.error_message = error_message

            command.save()
