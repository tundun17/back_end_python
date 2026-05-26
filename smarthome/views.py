import json

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mqtt_client.handlers import handle_inbound_message
from mqtt_client.client import MQTTClientError
from mqtt_client.services import MQTTServiceError, normalize_state, publish_control_command

from .models import Alert as AlertModel
from .models import DeviceCommand as DeviceCommandModel
from .models import ESP as ESPModel
from .models import Home as HomeModel
from .models import MQTTMessage as MQTTMessageModel
from .models import Room as RoomModel
from .models import SensorReading as SensorReadingModel
from .models import Switch as SwitchModel


def index(request):
    return HttpResponse("Xin chao. <br>Ban da den trang Smart Home Backend")


def get_request_owner(request):
    if request.user.is_authenticated:
        return request.user

    User = get_user_model()
    user, _ = User.objects.get_or_create(username="demo_user")
    return user


def missing_fields(body, required_fields):
    return [field for field in required_fields if field not in body]


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
        "name": room.name,
        "floor": room.floor,
        "description": room.description,
        "created_at": room.created_at,
        "updated_at": room.updated_at,
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
        "switch_id": command.switch_id,
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
        "temperature": reading.temperature,
        "humidity": reading.humidity,
        "gas": reading.gas,
        "recorded_at": reading.recorded_at,
        "created_at": reading.created_at,
    }


def home_overview_to_dict(home):
    esps = ESPModel.objects.filter(home=home)
    switches = SwitchModel.objects.filter(esp_device__home=home)
    alerts = AlertModel.objects.filter(device__home=home)

    return {
        "home": {
            "id": home.id,
            "name": home.name,
            "address": home.address,
        },
        "rooms": {
            "total": RoomModel.objects.filter(home=home).count(),
        },
        "esps": {
            "total": esps.count(),
            "online": esps.filter(status=ESPModel.Status.ONLINE).count(),
            "offline": esps.filter(status=ESPModel.Status.OFFLINE).count(),
            "unclaimed": esps.filter(status=ESPModel.Status.UNCLAIMED).count(),
            "error": esps.filter(status=ESPModel.Status.ERROR).count(),
            "sensors": esps.filter(is_sensor=True).count(),
            "controllers": esps.filter(is_sensor=False).count(),
        },
        "switches": {
            "total": switches.count(),
            "on": switches.filter(actual_state=SwitchModel.State.ON).count(),
            "off": switches.filter(actual_state=SwitchModel.State.OFF).count(),
            "pending": switches.filter(sync_status=SwitchModel.SyncStatus.PENDING).count(),
            "failed": switches.filter(sync_status=SwitchModel.SyncStatus.FAILED).count(),
            "synced": switches.filter(sync_status=SwitchModel.SyncStatus.SYNCED).count(),
        },
        "alerts": {
            "total": alerts.count(),
            "unresolved": alerts.filter(is_resolved=False).count(),
            "resolved": alerts.filter(is_resolved=True).count(),
            "critical": alerts.filter(severity=AlertModel.Severity.CRITICAL, is_resolved=False).count(),
            "high": alerts.filter(severity=AlertModel.Severity.HIGH, is_resolved=False).count(),
        },
        "updated_at": timezone.now(),
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        body = request.data

        required_fields = ["username", "password", "password_confirm"]
        missing = missing_fields(body, required_fields)
        if missing:
            return Response(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        username = body["username"]
        email = body.get("email", "")
        password = body["password"]
        password_confirm = body["password_confirm"]
        first_name = body.get("first_name", "")
        last_name = body.get("last_name", "")

        if password != password_confirm:
            return Response(
                {"message": "Mat khau xac nhan khong khop"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            return Response(
                {"message": "Username da ton tai"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if email and User.objects.filter(email=email).exists():
            return Response(
                {"message": "Email da ton tai"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(password)
        except ValidationError as exc:
            return Response(
                {"message": "Mat khau khong hop le", "errors": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        return Response(
            {"message": "Dang ky tai khoan thanh cong", "data": user_to_dict(user)},
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {"message": "JWT logout phia server khong luu session. Frontend chi can xoa access/refresh token."},
            status=status.HTTP_200_OK,
        )


class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(user_to_dict(request.user), status=status.HTTP_200_OK)

    def patch(self, request):
        body = request.data

        user = request.user
        email = body.get("email", user.email)

        User = get_user_model()
        if email and User.objects.exclude(id=user.id).filter(email=email).exists():
            return Response(
                {"message": "Email da duoc su dung"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "email" in body:
            user.email = email
        if "first_name" in body:
            user.first_name = body["first_name"]
        if "last_name" in body:
            user.last_name = body["last_name"]

        user.save(update_fields=["email", "first_name", "last_name"])
        return Response(
            {"message": "Cap nhat user thanh cong", "data": user_to_dict(user)},
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        body = request.data

        required_fields = ["old_password", "new_password", "new_password_confirm"]
        missing = missing_fields(body, required_fields)
        if missing:
            return Response(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if not user.check_password(body["old_password"]):
            return Response(
                {"message": "Mat khau cu khong dung"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if body["new_password"] != body["new_password_confirm"]:
            return Response(
                {"message": "Mat khau xac nhan khong khop"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(body["new_password"], user=user)
        except ValidationError as exc:
            return Response(
                {"message": "Mat khau khong hop le", "errors": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(body["new_password"])
        user.save(update_fields=["password"])
        return Response({"message": "Doi mat khau thanh cong"}, status=status.HTTP_200_OK)


class HomeView(APIView):
    def get(self, request):
        owner = get_request_owner(request)
        homes = HomeModel.objects.filter(owner=owner).values(
            "id",
            "name",
            "address",
            "description",
            "created_at",
            "updated_at",
        )
        return Response(list(homes), status=status.HTTP_200_OK)

    def post(self, request):
        body = request.data

        required_fields = ["name"]
        missing = missing_fields(body, required_fields)
        if missing:
            return Response(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not body["name"]:
            return Response({"message": "Ten nha khong duoc de trong"}, status=status.HTTP_400_BAD_REQUEST)

        home = HomeModel.objects.create(
            owner=get_request_owner(request),
            name=body["name"],
            address=body.get("address", ""),
            description=body.get("description", ""),
        )

        return Response(
            {
                "message": "Them nha thanh cong",
                "data": {
                    "id": home.id,
                    "name": home.name,
                    "address": home.address,
                    "description": home.description,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class HomeDetailView(APIView):
    def get(self, request, home_id):
        owner = get_request_owner(request)
        try:
            home = HomeModel.objects.get(id=home_id, owner=owner)
        except HomeModel.DoesNotExist:
            return Response({"message": "Nha khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        return Response(home_to_dict(home), status=status.HTTP_200_OK)

    def patch(self, request, home_id):
        body = request.data

        owner = get_request_owner(request)
        try:
            home = HomeModel.objects.get(id=home_id, owner=owner)
        except HomeModel.DoesNotExist:
            return Response({"message": "Nha khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        if "name" in body:
            if not body["name"]:
                return Response({"message": "Ten nha khong duoc de trong"}, status=status.HTTP_400_BAD_REQUEST)
            home.name = body["name"]
        if "address" in body:
            home.address = body["address"]
        if "description" in body:
            home.description = body["description"]

        home.save()
        return Response({"message": "Cap nhat nha thanh cong", "data": home_to_dict(home)}, status=status.HTTP_200_OK)

    def delete(self, request, home_id):
        owner = get_request_owner(request)
        try:
            home = HomeModel.objects.get(id=home_id, owner=owner)
        except HomeModel.DoesNotExist:
            return Response({"message": "Nha khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        home.delete()
        return Response({"message": "Xoa nha thanh cong"}, status=status.HTTP_200_OK)


class HomeOverviewView(APIView):
    def get(self, request, home_id):
        owner = get_request_owner(request)
        try:
            home = HomeModel.objects.get(id=home_id, owner=owner)
        except HomeModel.DoesNotExist:
            return Response({"message": "Nha khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        return Response(home_overview_to_dict(home), status=status.HTTP_200_OK)


class RoomView(APIView):
    def get(self, request, home_id):
        owner = get_request_owner(request)
        if not HomeModel.objects.filter(id=home_id, owner=owner).exists():
            return Response({"message": "Nha khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        rooms = RoomModel.objects.filter(home_id=home_id).values(
            "id",
            "home_id",
            "name",
            "floor",
            "description",
            "created_at",
            "updated_at",
        )
        return Response(list(rooms), status=status.HTTP_200_OK)

    def post(self, request, home_id):
        body = request.data

        owner = get_request_owner(request)
        if not HomeModel.objects.filter(id=home_id, owner=owner).exists():
            return Response({"message": "Nha khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        required_fields = ["name"]
        missing = missing_fields(body, required_fields)
        if missing:
            return Response(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not body["name"]:
            return Response({"message": "Ten phong khong duoc de trong"}, status=status.HTTP_400_BAD_REQUEST)

        if RoomModel.objects.filter(home_id=home_id, name=body["name"]).exists():
            return Response({"message": "Phong da ton tai trong nha nay"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            floor = int(body.get("floor", 1))
        except (TypeError, ValueError):
            return Response({"message": "Tang phai la so nguyen"}, status=status.HTTP_400_BAD_REQUEST)

        room = RoomModel.objects.create(
            home_id=home_id,
            name=body["name"],
            floor=floor,
            description=body.get("description", ""),
        )

        return Response(
            {
                "message": "Them phong thanh cong",
                "data": {
                    "id": room.id,
                    "home_id": room.home_id,
                    "name": room.name,
                    "floor": room.floor,
                    "description": room.description,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class RoomDetailView(APIView):
    def get(self, request, home_id, room_id):
        owner = get_request_owner(request)
        try:
            room = RoomModel.objects.get(id=room_id, home_id=home_id, home__owner=owner)
        except RoomModel.DoesNotExist:
            return Response({"message": "Phong khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        return Response(room_to_dict(room), status=status.HTTP_200_OK)

    def patch(self, request, home_id, room_id):
        body = request.data

        owner = get_request_owner(request)
        try:
            room = RoomModel.objects.get(id=room_id, home_id=home_id, home__owner=owner)
        except RoomModel.DoesNotExist:
            return Response({"message": "Phong khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        if "name" in body:
            if not body["name"]:
                return Response({"message": "Ten phong khong duoc de trong"}, status=status.HTTP_400_BAD_REQUEST)
            if RoomModel.objects.filter(home_id=room.home_id, name=body["name"]).exclude(id=room.id).exists():
                return Response({"message": "Phong da ton tai trong nha nay"}, status=status.HTTP_400_BAD_REQUEST)
            room.name = body["name"]
        if "floor" in body:
            try:
                room.floor = int(body["floor"])
            except (TypeError, ValueError):
                return Response({"message": "Tang phai la so nguyen"}, status=status.HTTP_400_BAD_REQUEST)
        if "description" in body:
            room.description = body["description"]

        room.save()
        return Response({"message": "Cap nhat phong thanh cong", "data": room_to_dict(room)}, status=status.HTTP_200_OK)

    def delete(self, request, home_id, room_id):
        owner = get_request_owner(request)
        try:
            room = RoomModel.objects.get(id=room_id, home_id=home_id, home__owner=owner)
        except RoomModel.DoesNotExist:
            return Response({"message": "Phong khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        room.delete()
        return Response({"message": "Xoa phong thanh cong"}, status=status.HTTP_200_OK)


class ESPView(APIView):
    def get(self, request):
        esps = ESPModel.objects.select_related("home", "room").values(
            "id",
            "home_id",
            "room_id",
            "hashcode",
            "esp_name",
            "is_sensor",
            "status",
            "ip_address",
            "firmware_version",
            "last_seen_at",
            "created_at",
            "updated_at",
        )
        return Response(list(esps), status=status.HTTP_200_OK)

    def post(self, request):
        body = request.data

        required_fields = ["home_id", "hashcode", "name"]
        missing = missing_fields(body, required_fields)
        if missing:
            return Response(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not HomeModel.objects.filter(id=body["home_id"]).exists():
            return Response({"message": "Nha khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        room_id = body.get("room_id")
        if room_id is not None:
            if not RoomModel.objects.filter(id=room_id, home_id=body["home_id"]).exists():
                return Response({"message": "Phong khong thuoc nha nay"}, status=status.HTTP_400_BAD_REQUEST)

        if ESPModel.objects.filter(hashcode=body["hashcode"]).exists():
            return Response({"message": "Hashcode ESP da ton tai"}, status=status.HTTP_400_BAD_REQUEST)

        esp = ESPModel.objects.create(
            home_id=body["home_id"],
            room_id=room_id,
            hashcode=body["hashcode"],
            esp_name=body["name"],
            is_sensor=bool(body.get("is_sensor", False)),
        )

        return Response(
            {
                "message": "Them ESP thanh cong",
                "data": {
                    "id": esp.id,
                    "home_id": esp.home_id,
                    "room_id": esp.room_id,
                    "hashcode": esp.hashcode,
                    "name": esp.esp_name,
                    "is_sensor": esp.is_sensor,
                    "status": esp.status,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class ESPDetailView(APIView):
    def get(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return Response({"message": "ESP khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        return Response(esp_to_dict(esp), status=status.HTTP_200_OK)

    def patch(self, request, hashcode):
        body = request.data

        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return Response({"message": "ESP khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        if "name" in body:
            esp.esp_name = body["name"]

        if "is_sensor" in body:
            if not isinstance(body["is_sensor"], bool):
                return Response({"message": "is_sensor phai la true hoac false"}, status=status.HTTP_400_BAD_REQUEST)
            esp.is_sensor = body["is_sensor"]

        if "home_id" in body:
            if not HomeModel.objects.filter(id=body["home_id"]).exists():
                return Response({"message": "Nha khong ton tai"}, status=status.HTTP_404_NOT_FOUND)
            esp.home_id = body["home_id"]

            if esp.room_id and not RoomModel.objects.filter(id=esp.room_id, home_id=esp.home_id).exists():
                esp.room_id = None

        if "room_id" in body:
            room_id = body["room_id"]
            if room_id is None:
                esp.room_id = None
            else:
                if not RoomModel.objects.filter(id=room_id, home_id=esp.home_id).exists():
                    return Response({"message": "Phong khong thuoc nha nay"}, status=status.HTTP_400_BAD_REQUEST)
                esp.room_id = room_id

        esp.save()
        return Response({"message": "Cap nhat ESP thanh cong", "data": esp_to_dict(esp)}, status=status.HTTP_200_OK)

    def delete(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return Response({"message": "ESP khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        esp.delete()
        return Response({"message": "Xoa ESP thanh cong"}, status=status.HTTP_200_OK)


class ESPMQTTMessageView(APIView):
    def get(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return Response({"message": "ESP khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        messages = MQTTMessageModel.objects.filter(device=esp)
        return Response(
            [mqtt_message_to_dict(message) for message in messages],
            status=status.HTTP_200_OK,
        )


class ESPSensorLatestView(APIView):
    def get(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return Response({"message": "ESP khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        reading = SensorReadingModel.objects.filter(device=esp).first()
        if reading is None:
            return Response({"message": "Chua co du lieu sensor"}, status=status.HTTP_404_NOT_FOUND)

        return Response(sensor_reading_to_dict(reading), status=status.HTTP_200_OK)


class ESPSensorHistoryView(APIView):
    def get(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return Response({"message": "ESP khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        limit = int(request.GET.get("limit", 30))
        readings = SensorReadingModel.objects.filter(device=esp)[:limit]
        return Response([sensor_reading_to_dict(reading) for reading in readings], status=status.HTTP_200_OK)


class DebugMQTTInboundView(APIView):
    def post(self, request):
        body = request.data

        missing = missing_fields(body, ["topic", "payload"])
        if missing:
            return Response(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(body["payload"], dict):
            return Response({"message": "payload phai la JSON object"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            mqtt_log = handle_inbound_message(body["topic"], json.dumps(body["payload"]))
        except Exception as exc:
            return Response(
                {"message": "Xu ly MQTT inbound that bai", "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Xu ly MQTT inbound thanh cong",
                "data": mqtt_message_to_dict(mqtt_log),
            },
            status=status.HTTP_201_CREATED,
        )


class SwitchView(APIView):
    def get(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return Response({"message": "ESP khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        switches = SwitchModel.objects.filter(esp_device=esp)
        return Response([switch_to_dict(switch) for switch in switches], status=status.HTTP_200_OK)


class SwitchDetailView(APIView):
    def get(self, request, hashcode, switch_code):
        try:
            switch = SwitchModel.objects.get(switch_code=switch_code, esp_device__hashcode=hashcode)
        except SwitchModel.DoesNotExist:
            return Response({"message": "Switch khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        return Response(switch_to_dict(switch), status=status.HTTP_200_OK)

    def patch(self, request, hashcode, switch_code):
        body = request.data

        try:
            switch = SwitchModel.objects.get(switch_code=switch_code, esp_device__hashcode=hashcode)
        except SwitchModel.DoesNotExist:
            return Response({"message": "Switch khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        if set(body) != {"switch_name"}:
            return Response({"message": "Chi duoc phep cap nhat switch_name"}, status=status.HTTP_400_BAD_REQUEST)

        switch.switch_name = body["switch_name"]
        switch.save(update_fields=["switch_name", "updated_at"])
        return Response({"message": "Cap nhat switch thanh cong", "data": switch_to_dict(switch)}, status=status.HTTP_200_OK)


class SwitchControlView(APIView):
    def post(self, request, hashcode, switch_code):
        body = request.data

        if set(body) != {"state"}:
            return Response({"message": "Payload chi chap nhan field state"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            state = normalize_state(body["state"])
        except MQTTServiceError as exc:
            return Response({"message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            switch = SwitchModel.objects.select_related("esp_device").get(
                switch_code=switch_code,
                esp_device__hashcode=hashcode,
            )
        except SwitchModel.DoesNotExist:
            return Response({"message": "Switch khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        command = DeviceCommandModel.objects.create(
            esp=switch.esp_device,
            switch=switch,
            command_type="SET_DEVICE_STATE",
            command_value=state,
            status=DeviceCommandModel.CommandStatus.PENDING,
            created_by=get_request_owner(request),
        )

        try:
            publish_result = publish_control_command(
                hashcode=hashcode,
                command_id=command.id,
                switch_code=switch.switch_code,
                state=state,
            )
        except (MQTTClientError, MQTTServiceError) as exc:
            command.status = DeviceCommandModel.CommandStatus.FAILED
            command.error_message = str(exc)
            command.save(update_fields=["status", "error_message"])
            return Response(
                {
                    "message": "Publish MQTT that bai",
                    "data": command_to_dict(command),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        command.status = DeviceCommandModel.CommandStatus.PUBLISHED
        command.published_at = timezone.now()
        command.save(update_fields=["status", "published_at"])

        switch.desired_state = state
        switch.sync_status = SwitchModel.SyncStatus.PENDING
        switch.last_controlled_at = timezone.now()
        switch.save(update_fields=["desired_state", "sync_status", "last_controlled_at", "updated_at"])

        return Response(
            {
                "message": "Gui lenh dieu khien thanh cong",
                "data": {
                    "command": command_to_dict(command),
                    "switch": switch_to_dict(switch),
                    "mqtt": publish_result,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class SwitchCommandView(APIView):
    def get(self, request, hashcode, switch_code):
        try:
            switch = SwitchModel.objects.get(
                switch_code=switch_code,
                esp_device__hashcode=hashcode,
            )
        except SwitchModel.DoesNotExist:
            return Response({"message": "Switch khong ton tai"}, status=status.HTTP_404_NOT_FOUND)

        commands = DeviceCommandModel.objects.filter(
            esp=switch.esp_device,
            switch=switch,
        )
        return Response([command_to_dict(command) for command in commands], status=status.HTTP_200_OK)
