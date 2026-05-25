from django.apps import apps
from django.conf import settings
from django.core.validators import validate_ipv46_address
from django.utils import timezone

from .services import (
    MQTTServiceError,
    detect_message_type,
    extract_hashcode_from_topic,
    log_mqtt_message,
    parse_payload,
    publish_ack_command,
)


def get_model_or_none(model_path: str):
    try:
        app_label, model_name = model_path.split(".")
        return apps.get_model(app_label, model_name)
    except Exception:
        return None


def get_esp_model():
    return get_model_or_none(getattr(settings, "MQTT_ESP_MODEL", "smarthome.ESP"))


def get_switch_model():
    return get_model_or_none(getattr(settings, "MQTT_DEVICE_MODEL", "smarthome.Switch"))


def get_sensor_reading_model():
    return get_model_or_none(
        getattr(settings, "MQTT_SENSOR_READING_MODEL", "smarthome.SensorReading")
    )


def get_alert_model():
    return get_model_or_none(getattr(settings, "MQTT_ALERT_MODEL", "smarthome.Alert"))


def get_command_model():
    return get_model_or_none(
        getattr(settings, "MQTT_COMMAND_MODEL", "smarthome.DeviceCommand")
    )


def set_field_if_exists(instance, field_name: str, value):
    if hasattr(instance, field_name):
        setattr(instance, field_name, value)


def get_esp_by_hashcode(hashcode: str | None):
    ESP = get_esp_model()
    if ESP is None or not hashcode:
        return None
    return ESP.objects.filter(hashcode=hashcode).first()


def update_esp_online(esp, data: dict | None = None):
    if esp is None:
        return

    data = data or {}
    set_field_if_exists(esp, "status", "ONLINE")
    set_field_if_exists(esp, "last_seen_at", timezone.now())

    for field_name in ["ip_address", "firmware_version"]:
        if data.get(field_name):
            set_field_if_exists(esp, field_name, data[field_name])

    if "is_sensor" in data:
        set_field_if_exists(esp, "is_sensor", data["is_sensor"])

    esp.save()


def sync_switches_from_syn(esp, num_switches: int):
    Switch = get_switch_model()
    if Switch is None:
        return

    for number in range(1, num_switches + 1):
        switch_code = f"device_{number}"
        Switch.objects.get_or_create(
            esp_device=esp,
            switch_code=switch_code,
            defaults={
                "switch_name": "",
            },
        )


def handle_inbound_message(topic: str, payload_text: str):
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
            raise MQTTServiceError(f"Topic chua duoc ho tro: {topic}")

        mqtt_log.is_processed = True
        mqtt_log.save(update_fields=["is_processed"])
        return mqtt_log

    except Exception as exc:
        try:
            log_mqtt_message(
                topic=topic,
                direction="INBOUND",
                message_type=message_type,
                device_hashcode=extract_hashcode_from_topic(topic, None),
                payload={"raw": payload_text},
                is_processed=False,
                error_message=str(exc),
            )
        except Exception:
            pass
        raise


def handle_syn(payload: dict):
    allowed_fields = {
        "hashcode",
        "ip_address",
        "firmware_version",
        "is_sensor",
        "num_switches",
    }
    required_fields = {
        "hashcode",
        "ip_address",
        "firmware_version",
        "is_sensor",
        "num_switches",
    }

    extra_fields = set(payload) - allowed_fields
    if extra_fields:
        raise MQTTServiceError(
            f"Payload syn chi chap nhan cac field: {sorted(allowed_fields)}"
        )

    missing_fields = required_fields - set(payload)
    if missing_fields:
        raise MQTTServiceError(
            f"Payload syn thieu field: {sorted(missing_fields)}"
        )

    hashcode = payload.get("hashcode")
    validate_ipv46_address(payload["ip_address"])

    if not isinstance(payload["is_sensor"], bool):
        raise MQTTServiceError("Payload syn field is_sensor phai la boolean")

    if isinstance(payload["num_switches"], bool) or not isinstance(payload["num_switches"], int):
        raise MQTTServiceError("Payload syn field num_switches phai la so nguyen")

    if payload["num_switches"] < 0:
        raise MQTTServiceError("Payload syn field num_switches phai lon hon hoac bang 0")

    esp = get_esp_by_hashcode(hashcode)
    if esp is None:
        raise MQTTServiceError(f"Khong tim thay ESP voi hashcode={hashcode}")

    update_esp_online(esp, payload)

    if not payload["is_sensor"]:
        sync_switches_from_syn(esp, payload["num_switches"])

    publish_ack_command(hashcode=hashcode)


def handle_sensor(topic: str, payload: dict):
    allowed_fields = {"temperature", "humidity", "gas"}
    required_fields = {"temperature", "humidity", "gas"}

    extra_fields = set(payload) - allowed_fields
    if extra_fields:
        raise MQTTServiceError(
            f"Payload sensor chi chap nhan cac field: {sorted(allowed_fields)}"
        )

    missing_fields = required_fields - set(payload)
    if missing_fields:
        raise MQTTServiceError(
            f"Payload sensor thieu field: {sorted(missing_fields)}"
        )

    hashcode = extract_hashcode_from_topic(topic, payload)
    esp = get_esp_by_hashcode(hashcode)
    if esp is None:
        raise MQTTServiceError(f"Khong tim thay ESP voi hashcode={hashcode}")

    update_esp_online(esp)

    SensorReading = get_sensor_reading_model()
    if SensorReading is None:
        return

    temperature = float(payload.get("temperature", 0) or 0)
    humidity = float(payload.get("humidity", 0) or 0)
    gas = float(payload.get("gas", 0) or 0)

    reading = SensorReading.objects.create(
        device=esp,
        temperature=temperature,
        humidity=humidity,
        gas=gas,
    )

    create_alerts_if_needed(
        device=esp,
        reading=reading,
        temperature=temperature,
        gas=gas,
    )


def create_alerts_if_needed(
    device,
    reading,
    temperature: float,
    gas: float,
):
    Alert = get_alert_model()
    if Alert is None:
        return

    smoke_threshold = getattr(settings, "SMOKE_THRESHOLD", 800)
    temperature_threshold = getattr(settings, "TEMPERATURE_THRESHOLD", 45)

    if gas >= smoke_threshold:
        Alert.objects.create(
            device=device,
            sensor_reading=reading,
            alert_type="SMOKE_DETECTED",
            severity="CRITICAL",
            message="Gas value is higher than safe threshold",
            threshold_value=smoke_threshold,
            actual_value=gas,
        )

    if temperature >= temperature_threshold:
        Alert.objects.create(
            device=device,
            sensor_reading=reading,
            alert_type="HIGH_TEMPERATURE",
            severity="HIGH",
            message="Temperature is higher than safe threshold",
            threshold_value=temperature_threshold,
            actual_value=temperature,
        )


def handle_state(topic: str, payload: dict):
    hashcode = extract_hashcode_from_topic(topic, payload)
    esp = get_esp_by_hashcode(hashcode)
    if esp is None:
        raise MQTTServiceError(f"Khong tim thay ESP voi hashcode={hashcode}")

    update_esp_online(esp)

    switch_code = payload.get("switch_code") or payload.get("device_code")
    actual_state = payload.get("actual_state")
    success = bool(payload.get("success", True))
    command_id = payload.get("command_id")
    error_message = payload.get("error_message")

    if not switch_code:
        raise MQTTServiceError("Payload state thieu switch_code")

    if actual_state not in ["ON", "OFF"]:
        raise MQTTServiceError("actual_state phai la ON hoac OFF")

    Switch = get_switch_model()
    switch = None

    if Switch is not None:
        switch = Switch.objects.filter(
            esp_device=esp,
            switch_code=switch_code,
        ).first()

        if switch is not None:
            switch.actual_state = actual_state
            switch.sync_status = "SYNCED" if success else "FAILED"
            switch.save(update_fields=["actual_state", "sync_status", "updated_at"])

    Command = get_command_model()
    if Command is not None and command_id:
        command = Command.objects.filter(id=command_id).first()
        if command is not None:
            command.status = "DONE" if success else "FAILED"
            command.acknowledged_at = timezone.now()
            if hasattr(command, "error_message"):
                command.error_message = error_message or ""
            command.save()
