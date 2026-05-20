import json
from typing import Any

from django.apps import apps

from .client import publish_json
from smarthome.models import MQTTMessage


class MQTTServiceError(Exception):
    pass


def normalize_state(state: Any) -> str:
    """
    Chuẩn hóa trạng thái đèn theo tài liệu: ON/OFF.
    """
    if isinstance(state, bool):
        return "ON" if state else "OFF"

    if isinstance(state, int):
        if state == 1:
            return "ON"
        if state == 0:
            return "OFF"

    if isinstance(state, str):
        value = state.strip().upper()

        if value in ["ON", "1", "TRUE"]:
            return "ON"

        if value in ["OFF", "0", "FALSE"]:
            return "OFF"

    raise MQTTServiceError("state chỉ được là ON, OFF, 1, 0, true hoặc false")


def validate_topic_part(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise MQTTServiceError(f"{field_name} phải là chuỗi")

    value = value.strip()

    if not value:
        raise MQTTServiceError(f"{field_name} không được rỗng")

    for char in ["/", "#", "+", " "]:
        if char in value:
            raise MQTTServiceError(f"{field_name} không được chứa ký tự '{char}'")

    return value


def build_device_topic(hashcode: str, topic_type: str) -> str:
    """
    Chuẩn topic:
    {hashcode}/set
    {hashcode}/sensor
    {hashcode}/state
    """
    hashcode = validate_topic_part(hashcode, "hashcode")
    topic_type = validate_topic_part(topic_type, "topic_type")

    allowed = ["set", "sensor", "state", "syn", "ack"]

    if topic_type not in allowed:
        raise MQTTServiceError(f"topic_type chỉ được là: {allowed}")

    return f"{hashcode}/{topic_type}"


def detect_message_type(topic: str) -> str:
    if topic == "syn":
        return "SYN"

    if topic == "ack":
        return "ACK"

    if topic.endswith("/sensor"):
        return "SENSOR"

    if topic.endswith("/state"):
        return "STATE"

    if topic.endswith("/set"):
        return "SET"

    return "UNKNOWN"


def extract_hashcode_from_topic(topic: str, payload: dict | None = None) -> str | None:
    """
    Với topic:
    - syn: lấy hashcode từ payload
    - ack: lấy hashcode từ payload
    - ESP_ABC123/sensor: lấy ESP_ABC123 từ topic
    - ESP_ABC123/state: lấy ESP_ABC123 từ topic
    - ESP_ABC123/set: lấy ESP_ABC123 từ topic
    """
    if topic == "syn" or topic == "ack":
        if payload:
            return payload.get("hashcode")
        return None

    parts = topic.split("/")

    if len(parts) >= 2:
        return parts[0]

    return None


def log_mqtt_message(
    topic: str,
    direction: str,
    payload: dict,
    message_type: str | None = None,
    device_hashcode: str | None = None,
    is_processed: bool = False,
    error_message: str | None = None,
) -> MQTTMessage:
    if message_type is None:
        message_type = detect_message_type(topic)

    if device_hashcode is None:
        device_hashcode = extract_hashcode_from_topic(topic, payload)

    device = None
    if device_hashcode:
        ESP = apps.get_model("smarthome", "ESP")
        device = ESP.objects.filter(hashcode=device_hashcode).first()

    return MQTTMessage.objects.create(
        topic=topic,
        direction=direction,
        message_type=message_type,
        device=device,
        payload=payload,
        is_processed=is_processed,
        error_message=error_message,
    )


def publish_control_command(
    hashcode: str,
    command_id: int,
    switch_code: str,
    state: Any,
) -> dict:
    """
    Publish command xuống ESP32.

    Topic:
    ESP_ABC123/set

    Payload:
    {
        "command_id": 25,
        "command_type": "SET_DEVICE_STATE",
        "switch_code": "SWITCH_01",
        "state": "ON"
    }
    """
    hashcode = validate_topic_part(hashcode, "hashcode")
    switch_code = validate_topic_part(switch_code, "switch_code")
    state = normalize_state(state)

    topic = build_device_topic(hashcode, "set")

    payload = {
        "command_id": command_id,
        "command_type": "SET_DEVICE_STATE",
        "switch_code": switch_code,
        "state": state,
    }

    result = publish_json(topic=topic, payload=payload)

    log_mqtt_message(
        topic=topic,
        direction="OUTBOUND",
        message_type="SET",
        device_hashcode=hashcode,
        payload=payload,
        is_processed=True,
    )

    return result

def publish_ack_command(
    hashcode: str,
    command_id: int,
    ack_response: str,
) -> dict:
    """
    Publish command xuống ESP32.

    Topic:
    ESP_ABC123/ack

    Payload:
    {
        "command_id": 25,
        "command_type": "ACK_RESPONSE",
        "ack_response": "OK",
    }
    """
    hashcode = validate_topic_part(hashcode, "hashcode")
    ack_response = validate_topic_part(ack_response, "ack_response")

    topic = build_device_topic(hashcode, "ack")

    payload = {
        "command_id": command_id,
        "command_type": "ACK_RESPONSE",
        "ack_response": ack_response,
    }

    result = publish_json(topic=topic, payload=payload)

    log_mqtt_message(
        topic=topic,
        direction="OUTBOUND",
        message_type="ACK",
        device_hashcode=hashcode,
        payload=payload,
        is_processed=True,
    )

    return result


def parse_payload(payload_text: str) -> dict:
    try:
        data = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise MQTTServiceError(f"Payload không phải JSON hợp lệ: {exc}")

    if not isinstance(data, dict):
        raise MQTTServiceError("Payload MQTT phải là JSON object")

    return data
