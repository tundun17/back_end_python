import json
import ssl
import uuid

import paho.mqtt.client as mqtt
from django.conf import settings


class MQTTClientError(Exception):
    pass


def create_mqtt_client(client_id: str | None = None) -> mqtt.Client:
    """
    Tạo MQTT client dùng chung cho publish và worker subscribe.
    """
    if client_id is None:
        client_id = f"django-smart-home-{uuid.uuid4().hex[:8]}"

    client = mqtt.Client(client_id=client_id)

    username = getattr(settings, "MQTT_USERNAME", "")
    password = getattr(settings, "MQTT_PASSWORD", "")

    if username:
        client.username_pw_set(username=username, password=password)

    if getattr(settings, "MQTT_TLS", False):
        client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

    return client


def publish_json(
    topic: str,
    payload: dict,
    qos: int | None = None,
    retain: bool = False,
) -> dict:
    """
    Publish JSON message lên MQTT Broker.

    Ví dụ:
    topic: ESP_ABC123/set
    payload:
    {
        "command_id": 1,
        "command_type": "SET_DEVICE_STATE",
        "device_name": "DEVICE_01",
        "state": "ON"
    }
    """
    if qos is None:
        qos = getattr(settings, "MQTT_QOS", 0)

    try:
        payload_text = json.dumps(payload, ensure_ascii=False)
    except TypeError as exc:
        raise MQTTClientError(f"Payload không convert được sang JSON: {exc}")

    broker = settings.MQTT_BROKER
    port = settings.MQTT_PORT
    keepalive = getattr(settings, "MQTT_KEEPALIVE", 60)

    client = create_mqtt_client()

    try:
        client.connect(broker, port, keepalive=keepalive)
        client.loop_start()

        result = client.publish(
            topic=topic,
            payload=payload_text,
            qos=qos,
            retain=retain,
        )

        result.wait_for_publish(timeout=10)

        client.loop_stop()
        client.disconnect()

    except Exception as exc:
        raise MQTTClientError(
            f"Không publish được MQTT tới {broker}:{port}. Lỗi: {exc}"
        )

    return {
        "topic": topic,
        "payload": payload,
        "broker": broker,
        "port": port,
        "qos": qos,
        "retain": retain,
        "tls": getattr(settings, "MQTT_TLS", False),
    }
