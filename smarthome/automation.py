from django.conf import settings
from django.utils import timezone

from mqtt_client.client import MQTTClientError
from mqtt_client.services import MQTTServiceError, publish_control_command

from .models import Alert, AutomationRule, DeviceCommand, Switch


class AutomationService:
    def handle_sensor_reading(self, device, reading, temperature: float, humidity: float, gas: float):
        rules = AutomationRule.objects.select_related(
            "target_switch",
            "target_switch__esp_device",
        ).filter(
            sensor_device=device,
            enabled=True,
        )

        for rule in rules:
            is_active = self.is_rule_active(rule, temperature, humidity, gas)

            if is_active:
                self.activate_rule(rule)
            else:
                self.normalize_rule(rule)

    def is_rule_active(self, rule, temperature: float, humidity: float, gas: float):
        if rule.alert_type == Alert.AlertType.HIGH_TEMPERATURE:
            return temperature >= getattr(settings, "TEMPERATURE_THRESHOLD", 45)

        if rule.alert_type in [Alert.AlertType.SMOKE_DETECTED, Alert.AlertType.HIGH_SMOKE_LEVEL]:
            return gas >= getattr(settings, "SMOKE_THRESHOLD", 800)

        if rule.alert_type == Alert.AlertType.HIGH_HUMIDITY:
            return humidity >= getattr(settings, "HUMIDITY_THRESHOLD", 80)

        return False

    def activate_rule(self, rule):
        self.publish_state_if_needed(rule.target_switch, rule.active_state)
        rule.last_triggered_at = timezone.now()
        rule.save(update_fields=["last_triggered_at", "updated_at"])

    def normalize_rule(self, rule):
        active_alert = Alert.objects.filter(
            device=rule.sensor_device,
            alert_type=rule.alert_type,
            is_resolved=False,
        ).first()

        if active_alert is not None:
            active_alert.is_resolved = True
            active_alert.resolved_at = timezone.now()
            active_alert.save(update_fields=["is_resolved", "resolved_at"])

        self.publish_state_if_needed(rule.target_switch, rule.normal_state)
        rule.last_normalized_at = timezone.now()
        rule.save(update_fields=["last_normalized_at", "updated_at"])

    def publish_state_if_needed(self, switch, state: str):
        if switch.desired_state == state and switch.sync_status in [
            Switch.SyncStatus.SYNCED,
            Switch.SyncStatus.PENDING,
        ]:
            return None

        command = DeviceCommand.objects.create(
            esp=switch.esp_device,
            switch=switch,
            command_type="SET_DEVICE_STATE",
            command_value=state,
            status=DeviceCommand.CommandStatus.PENDING,
        )

        try:
            publish_result = publish_control_command(
                hashcode=switch.esp_device.hashcode,
                command_id=command.id,
                switch_code=switch.switch_code,
                state=state,
            )
        except (MQTTClientError, MQTTServiceError) as error:
            command.status = DeviceCommand.CommandStatus.FAILED
            command.error_message = str(error)
            command.save(update_fields=["status", "error_message"])
            return command

        command.status = DeviceCommand.CommandStatus.PUBLISHED
        command.published_at = timezone.now()
        command.save(update_fields=["status", "published_at"])

        switch.desired_state = state
        switch.sync_status = Switch.SyncStatus.PENDING
        switch.last_controlled_at = timezone.now()
        switch.save(
            update_fields=[
                "desired_state",
                "sync_status",
                "last_controlled_at",
                "updated_at",
            ]
        )

        return publish_result
