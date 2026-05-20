from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from mqtt_client.client import create_mqtt_client
from mqtt_client.handlers import handle_inbound_message


class Command(BaseCommand):
    help = "Run MQTT worker to receive messages from ESP32"

    def handle(self, *args, **options):
        client = create_mqtt_client(client_id="django-mqtt-worker")

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                self.stdout.write(self.style.SUCCESS("MQTT connected successfully"))

                client.subscribe("syn", qos=settings.MQTT_QOS)
                client.subscribe("+/sensor", qos=settings.MQTT_QOS)
                client.subscribe("+/state", qos=settings.MQTT_QOS)

                self.stdout.write("Subscribed topics: syn, +/sensor, +/state")
            else:
                self.stderr.write(f"MQTT connection failed. rc={rc}")

        def on_message(client, userdata, msg):
            close_old_connections()

            topic = msg.topic
            payload_text = msg.payload.decode("utf-8", errors="replace")

            self.stdout.write(f"[MQTT IN] {topic}: {payload_text}")

            try:
                handle_inbound_message(topic, payload_text)
                self.stdout.write(self.style.SUCCESS("Processed successfully"))

            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"Process failed: {exc}"))

        client.on_connect = on_connect
        client.on_message = on_message

        broker = settings.MQTT_BROKER
        port = settings.MQTT_PORT
        keepalive = settings.MQTT_KEEPALIVE

        self.stdout.write(f"Connecting to MQTT broker {broker}:{port}")

        try:
            client.connect(broker, port, keepalive=keepalive)
            client.loop_forever()

        except KeyboardInterrupt:
            self.stdout.write("Stopping MQTT worker...")
            client.disconnect()

        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"MQTT worker error: {exc}"))