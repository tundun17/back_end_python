from django.db import models

# Create your models here.
from django.db import models


class MQTTMessage(models.Model):
    DIRECTION_CHOICES = [
        ("INBOUND", "INBOUND"),
        ("OUTBOUND", "OUTBOUND"),
    ]

    MESSAGE_TYPE_CHOICES = [
        ("SYN", "SYN"),
        ("ACK", "ACK"),
        ("SENSOR", "SENSOR"),
        ("STATE", "STATE"),
        ("SET", "SET"),
        ("UNKNOWN", "UNKNOWN"),
    ]

    topic = models.CharField(max_length=255)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE_CHOICES,
        default="UNKNOWN",
    )

    # Giai doan dau dung hashcode de tranh phu thuoc qua chat vao model ESP.
    device_hashcode = models.CharField(max_length=100, null=True, blank=True)

    payload = models.JSONField(default=dict, blank=True)
    is_processed = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mqtt_messages"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.direction} {self.topic}"
