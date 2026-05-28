from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Alert, AutomationRule, ESP, Switch
from .views_common import automation_rule_to_dict, parse_boolean


class AutomationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rules = AutomationRule.objects.select_related(
            "sensor_device",
            "target_switch",
            "target_switch__esp_device",
        ).filter(sensor_device__home__owner=request.user)
        return Response([automation_rule_to_dict(rule) for rule in rules], status=status.HTTP_200_OK)

    def post(self, request):
        sensor_hashcode = request.data.get("sensor_hashcode")
        target_hashcode = request.data.get("target_hashcode")
        switch_code = request.data.get("switch_code")
        alert_type = request.data.get("alert_type")
        enabled = parse_boolean(request.data.get("enabled"), True)
        active_state = request.data.get("active_state", Switch.State.ON)
        normal_state = request.data.get("normal_state", Switch.State.OFF)

        required_fields = {
            "sensor_hashcode": sensor_hashcode,
            "target_hashcode": target_hashcode,
            "switch_code": switch_code,
            "alert_type": alert_type,
        }
        missing = [field for field, value in required_fields.items() if not value]
        if missing:
            return Response({"message": "Thieu du lieu.", "missing_fields": missing}, status=status.HTTP_400_BAD_REQUEST)
        if alert_type not in Alert.AlertType.values:
            return Response({"alert_type": "alert_type khong hop le."}, status=status.HTTP_400_BAD_REQUEST)
        if active_state not in Switch.State.values or normal_state not in Switch.State.values:
            return Response({"state": "active_state va normal_state phai la ON hoac OFF."}, status=status.HTTP_400_BAD_REQUEST)

        sensor_esp = get_object_or_404(ESP, hashcode=sensor_hashcode, home__owner=request.user)
        if not sensor_esp.is_sensor:
            return Response({"sensor_hashcode": "ESP nay khong phai sensor."}, status=status.HTTP_400_BAD_REQUEST)

        target_switch = get_object_or_404(
            Switch.objects.select_related("esp_device"),
            esp_device__hashcode=target_hashcode,
            esp_device__home__owner=request.user,
            switch_code=switch_code,
        )
        if target_switch.esp_device.home_id != sensor_esp.home_id:
            return Response({"message": "Sensor ESP va switch dieu khien phai thuoc cung mot nha."}, status=status.HTTP_400_BAD_REQUEST)

        rule, created = AutomationRule.objects.update_or_create(
            sensor_device=sensor_esp,
            target_switch=target_switch,
            alert_type=alert_type,
            defaults={
                "enabled": enabled,
                "active_state": active_state,
                "normal_state": normal_state,
            },
        )
        return Response(
            {
                "message": "Tao automation rule thanh cong." if created else "Cap nhat automation rule thanh cong.",
                "automation_rule": automation_rule_to_dict(rule),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AutomationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_rule(self, request, id):
        return get_object_or_404(
            AutomationRule.objects.select_related("sensor_device", "target_switch", "target_switch__esp_device"),
            id=id,
            sensor_device__home__owner=request.user,
        )

    def get(self, request, id):
        return Response(automation_rule_to_dict(self.get_rule(request, id)), status=status.HTTP_200_OK)

    def patch(self, request, id):
        rule = self.get_rule(request, id)

        if "enabled" in request.data:
            rule.enabled = parse_boolean(request.data.get("enabled"), rule.enabled)
        if "active_state" in request.data:
            if request.data["active_state"] not in Switch.State.values:
                return Response({"active_state": "active_state phai la ON hoac OFF."}, status=status.HTTP_400_BAD_REQUEST)
            rule.active_state = request.data["active_state"]
        if "normal_state" in request.data:
            if request.data["normal_state"] not in Switch.State.values:
                return Response({"normal_state": "normal_state phai la ON hoac OFF."}, status=status.HTTP_400_BAD_REQUEST)
            rule.normal_state = request.data["normal_state"]

        rule.save(update_fields=["enabled", "active_state", "normal_state", "updated_at"])
        return Response(
            {"message": "Cap nhat automation rule thanh cong.", "automation_rule": automation_rule_to_dict(rule)},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id):
        self.get_rule(request, id).delete()
        return Response({"message": "Xoa automation rule thanh cong."}, status=status.HTTP_200_OK)
