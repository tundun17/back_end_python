from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mqtt_client.client import MQTTClientError
from mqtt_client.services import MQTTServiceError, normalize_state, publish_control_command

from .models import DeviceCommand, ESP, Switch
from .serializers import command_to_dict, switch_to_dict


class SwitchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, hashcode):
        esp = get_object_or_404(ESP, hashcode=hashcode, home__owner=request.user)
        switches = Switch.objects.filter(esp_device=esp)
        return Response([switch_to_dict(switch) for switch in switches], status=status.HTTP_200_OK)


class SwitchDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_switch(self, request, hashcode, switch_code):
        return get_object_or_404(
            Switch,
            switch_code=switch_code,
            esp_device__hashcode=hashcode,
            esp_device__home__owner=request.user,
        )

    def get(self, request, hashcode, switch_code):
        return Response(switch_to_dict(self.get_switch(request, hashcode, switch_code)), status=status.HTTP_200_OK)

    def patch(self, request, hashcode, switch_code):
        switch = self.get_switch(request, hashcode, switch_code)
        if "switch_name" not in request.data:
            return Response({"switch_name": "Vui long nhap switch_name."}, status=status.HTTP_400_BAD_REQUEST)
        switch.switch_name = request.data.get("switch_name", "")
        switch.save(update_fields=["switch_name", "updated_at"])
        return Response({"message": "Cap nhat switch thanh cong.", "switch": switch_to_dict(switch)}, status=status.HTTP_200_OK)


class SwitchControlView(APIView):
    permission_classes = [IsAuthenticated]

    def get_switch(self, request, hashcode, switch_code):
        return get_object_or_404(
            Switch.objects.select_related("esp_device"),
            switch_code=switch_code,
            esp_device__hashcode=hashcode,
            esp_device__home__owner=request.user,
        )

    def post(self, request, hashcode, switch_code):
        state_input = request.data.get("state")
        if state_input is None:
            return Response({"state": "Vui long nhap state."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            state = normalize_state(state_input)
        except MQTTServiceError as error:
            return Response({"state": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        switch = self.get_switch(request, hashcode, switch_code)
        if state == "TOGGLE":
            state = Switch.State.OFF if switch.actual_state == Switch.State.ON else Switch.State.ON

        if state == switch.actual_state:
            command = DeviceCommand.objects.create(
                esp=switch.esp_device,
                switch=switch,
                command_type="SET_DEVICE_STATE",
                command_value=state,
                status=DeviceCommand.CommandStatus.FAILED,
                created_by=request.user,
                error_message=f"Trang thai hien tai da la {state}, khong publish xuong ESP.",
            )

            return Response(
                {
                    "message": "Trang thai yeu cau trung voi actual_state hien tai, khong gui lenh xuong ESP.",
                    "command": command_to_dict(command),
                    "switch": switch_to_dict(switch),
                },
                status=status.HTTP_409_CONFLICT,
            )
        command = DeviceCommand.objects.create(
            esp=switch.esp_device,
            switch=switch,
            command_type="SET_DEVICE_STATE",
            command_value=state,
            status=DeviceCommand.CommandStatus.PENDING,
            created_by=request.user,
        )

        try:
            publish_result = publish_control_command(
                hashcode=hashcode,
                command_id=command.id,
                switch_code=switch.switch_code,
                state=state,
            )
        except (MQTTClientError, MQTTServiceError) as error:
            command.status = DeviceCommand.CommandStatus.FAILED
            command.error_message = str(error)
            command.save(update_fields=["status", "error_message"])
            return Response(
                {"message": "Publish MQTT that bai.", "command": command_to_dict(command)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        command.status = DeviceCommand.CommandStatus.PUBLISHED
        command.published_at = timezone.now()
        command.save(update_fields=["status", "published_at"])

        switch.desired_state = state
        switch.sync_status = Switch.SyncStatus.PENDING
        switch.last_controlled_at = timezone.now()
        switch.save(update_fields=["desired_state", "sync_status", "last_controlled_at", "updated_at"])

        return Response(
            {
                "message": "Gui lenh dieu khien thanh cong.",
                "command": command_to_dict(command),
                "switch": switch_to_dict(switch),
                "mqtt": publish_result,
            },
            status=status.HTTP_201_CREATED,
        )


class SwitchCommandView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, hashcode, switch_code):
        switch = get_object_or_404(
            Switch,
            switch_code=switch_code,
            esp_device__hashcode=hashcode,
            esp_device__home__owner=request.user,
        )
        commands = DeviceCommand.objects.filter(esp=switch.esp_device, switch=switch)
        return Response([command_to_dict(command) for command in commands], status=status.HTTP_200_OK)
