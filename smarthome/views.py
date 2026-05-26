import json

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

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


def parse_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


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


@method_decorator(csrf_exempt, name="dispatch")
class RegisterView(View):
    def post(self, request):
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        required_fields = ["username", "password", "password_confirm"]
        missing = missing_fields(body, required_fields)
        if missing:
            return JsonResponse(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=400,
            )

        username = body["username"]
        email = body.get("email", "")
        password = body["password"]
        password_confirm = body["password_confirm"]
        first_name = body.get("first_name", "")
        last_name = body.get("last_name", "")

        if password != password_confirm:
            return JsonResponse({"message": "Mat khau xac nhan khong khop"}, status=400)

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            return JsonResponse({"message": "Username da ton tai"}, status=400)

        if email and User.objects.filter(email=email).exists():
            return JsonResponse({"message": "Email da ton tai"}, status=400)

        try:
            validate_password(password)
        except ValidationError as exc:
            return JsonResponse({"message": "Mat khau khong hop le", "errors": exc.messages}, status=400)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        return JsonResponse(
            {"message": "Dang ky tai khoan thanh cong", "data": user_to_dict(user)},
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class LoginView(View):
    def post(self, request):
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        missing = missing_fields(body, ["username", "password"])
        if missing:
            return JsonResponse(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=400,
            )

        user = authenticate(request, username=body["username"], password=body["password"])
        if user is None:
            return JsonResponse({"message": "Username hoac mat khau khong dung"}, status=400)

        login(request, user)
        return JsonResponse({"message": "Dang nhap thanh cong", "data": user_to_dict(user)})


@method_decorator(csrf_exempt, name="dispatch")
class LogoutView(View):
    def post(self, request):
        logout(request)
        return JsonResponse({"message": "Dang xuat thanh cong"})


@method_decorator(csrf_exempt, name="dispatch")
class UserMeView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"message": "Ban chua dang nhap"}, status=401)

        return JsonResponse(user_to_dict(request.user))

    def patch(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"message": "Ban chua dang nhap"}, status=401)

        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        user = request.user
        email = body.get("email", user.email)

        User = get_user_model()
        if email and User.objects.exclude(id=user.id).filter(email=email).exists():
            return JsonResponse({"message": "Email da duoc su dung"}, status=400)

        if "email" in body:
            user.email = email
        if "first_name" in body:
            user.first_name = body["first_name"]
        if "last_name" in body:
            user.last_name = body["last_name"]

        user.save(update_fields=["email", "first_name", "last_name"])
        return JsonResponse({"message": "Cap nhat user thanh cong", "data": user_to_dict(user)})


@method_decorator(csrf_exempt, name="dispatch")
class ChangePasswordView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"message": "Ban chua dang nhap"}, status=401)

        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        required_fields = ["old_password", "new_password", "new_password_confirm"]
        missing = missing_fields(body, required_fields)
        if missing:
            return JsonResponse(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=400,
            )

        user = request.user
        if not user.check_password(body["old_password"]):
            return JsonResponse({"message": "Mat khau cu khong dung"}, status=400)

        if body["new_password"] != body["new_password_confirm"]:
            return JsonResponse({"message": "Mat khau xac nhan khong khop"}, status=400)

        try:
            validate_password(body["new_password"], user=user)
        except ValidationError as exc:
            return JsonResponse({"message": "Mat khau khong hop le", "errors": exc.messages}, status=400)

        user.set_password(body["new_password"])
        user.save(update_fields=["password"])
        return JsonResponse({"message": "Doi mat khau thanh cong"})


@method_decorator(csrf_exempt, name="dispatch")
class HomeView(View):
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
        return JsonResponse(list(homes), safe=False)

    def post(self, request):
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        required_fields = ["name"]
        missing = missing_fields(body, required_fields)
        if missing:
            return JsonResponse(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=400,
            )

        if not body["name"]:
            return JsonResponse({"message": "Ten nha khong duoc de trong"}, status=400)

        home = HomeModel.objects.create(
            owner=get_request_owner(request),
            name=body["name"],
            address=body.get("address", ""),
            description=body.get("description", ""),
        )

        return JsonResponse(
            {
                "message": "Them nha thanh cong",
                "data": {
                    "id": home.id,
                    "name": home.name,
                    "address": home.address,
                    "description": home.description,
                },
            },
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class HomeDetailView(View):
    def get(self, request, home_id):
        owner = get_request_owner(request)
        try:
            home = HomeModel.objects.get(id=home_id, owner=owner)
        except HomeModel.DoesNotExist:
            return JsonResponse({"message": "Nha khong ton tai"}, status=404)

        return JsonResponse(home_to_dict(home))

    def patch(self, request, home_id):
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        owner = get_request_owner(request)
        try:
            home = HomeModel.objects.get(id=home_id, owner=owner)
        except HomeModel.DoesNotExist:
            return JsonResponse({"message": "Nha khong ton tai"}, status=404)

        if "name" in body:
            if not body["name"]:
                return JsonResponse({"message": "Ten nha khong duoc de trong"}, status=400)
            home.name = body["name"]
        if "address" in body:
            home.address = body["address"]
        if "description" in body:
            home.description = body["description"]

        home.save()
        return JsonResponse({"message": "Cap nhat nha thanh cong", "data": home_to_dict(home)})

    def delete(self, request, home_id):
        owner = get_request_owner(request)
        try:
            home = HomeModel.objects.get(id=home_id, owner=owner)
        except HomeModel.DoesNotExist:
            return JsonResponse({"message": "Nha khong ton tai"}, status=404)

        home.delete()
        return JsonResponse({"message": "Xoa nha thanh cong"})


@method_decorator(csrf_exempt, name="dispatch")
class HomeOverviewView(View):
    def get(self, request, home_id):
        owner = get_request_owner(request)
        try:
            home = HomeModel.objects.get(id=home_id, owner=owner)
        except HomeModel.DoesNotExist:
            return JsonResponse({"message": "Nha khong ton tai"}, status=404)

        return JsonResponse(home_overview_to_dict(home))


@method_decorator(csrf_exempt, name="dispatch")
class RoomView(View):
    def get(self, request, home_id):
        owner = get_request_owner(request)
        if not HomeModel.objects.filter(id=home_id, owner=owner).exists():
            return JsonResponse({"message": "Nha khong ton tai"}, status=404)

        rooms = RoomModel.objects.filter(home_id=home_id).values(
            "id",
            "home_id",
            "name",
            "floor",
            "description",
            "created_at",
            "updated_at",
        )
        return JsonResponse(list(rooms), safe=False)

    def post(self, request, home_id):
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        owner = get_request_owner(request)
        if not HomeModel.objects.filter(id=home_id, owner=owner).exists():
            return JsonResponse({"message": "Nha khong ton tai"}, status=404)

        required_fields = ["name"]
        missing = missing_fields(body, required_fields)
        if missing:
            return JsonResponse(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=400,
            )

        if not body["name"]:
            return JsonResponse({"message": "Ten phong khong duoc de trong"}, status=400)

        if RoomModel.objects.filter(home_id=home_id, name=body["name"]).exists():
            return JsonResponse({"message": "Phong da ton tai trong nha nay"}, status=400)

        try:
            floor = int(body.get("floor", 1))
        except (TypeError, ValueError):
            return JsonResponse({"message": "Tang phai la so nguyen"}, status=400)

        room = RoomModel.objects.create(
            home_id=home_id,
            name=body["name"],
            floor=floor,
            description=body.get("description", ""),
        )

        return JsonResponse(
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
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class RoomDetailView(View):
    def get(self, request, home_id, room_id):
        owner = get_request_owner(request)
        try:
            room = RoomModel.objects.get(id=room_id, home_id=home_id, home__owner=owner)
        except RoomModel.DoesNotExist:
            return JsonResponse({"message": "Phong khong ton tai"}, status=404)

        return JsonResponse(room_to_dict(room))

    def patch(self, request, home_id, room_id):
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        owner = get_request_owner(request)
        try:
            room = RoomModel.objects.get(id=room_id, home_id=home_id, home__owner=owner)
        except RoomModel.DoesNotExist:
            return JsonResponse({"message": "Phong khong ton tai"}, status=404)

        if "name" in body:
            if not body["name"]:
                return JsonResponse({"message": "Ten phong khong duoc de trong"}, status=400)
            if RoomModel.objects.filter(home_id=room.home_id, name=body["name"]).exclude(id=room.id).exists():
                return JsonResponse({"message": "Phong da ton tai trong nha nay"}, status=400)
            room.name = body["name"]
        if "floor" in body:
            try:
                room.floor = int(body["floor"])
            except (TypeError, ValueError):
                return JsonResponse({"message": "Tang phai la so nguyen"}, status=400)
        if "description" in body:
            room.description = body["description"]

        room.save()
        return JsonResponse({"message": "Cap nhat phong thanh cong", "data": room_to_dict(room)})

    def delete(self, request, home_id, room_id):
        owner = get_request_owner(request)
        try:
            room = RoomModel.objects.get(id=room_id, home_id=home_id, home__owner=owner)
        except RoomModel.DoesNotExist:
            return JsonResponse({"message": "Phong khong ton tai"}, status=404)

        room.delete()
        return JsonResponse({"message": "Xoa phong thanh cong"})


@method_decorator(csrf_exempt, name="dispatch")
class ESPView(View):
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
        return JsonResponse(list(esps), safe=False)

    def post(self, request):
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        required_fields = ["home_id", "hashcode", "name"]
        missing = missing_fields(body, required_fields)
        if missing:
            return JsonResponse(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=400,
            )

        if not HomeModel.objects.filter(id=body["home_id"]).exists():
            return JsonResponse({"message": "Nha khong ton tai"}, status=404)

        room_id = body.get("room_id")
        if room_id is not None:
            if not RoomModel.objects.filter(id=room_id, home_id=body["home_id"]).exists():
                return JsonResponse({"message": "Phong khong thuoc nha nay"}, status=400)

        if ESPModel.objects.filter(hashcode=body["hashcode"]).exists():
            return JsonResponse({"message": "Hashcode ESP da ton tai"}, status=400)

        esp = ESPModel.objects.create(
            home_id=body["home_id"],
            room_id=room_id,
            hashcode=body["hashcode"],
            esp_name=body["name"],
            is_sensor=bool(body.get("is_sensor", False)),
        )

        return JsonResponse(
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
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ESPDetailView(View):
    def get(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return JsonResponse({"message": "ESP khong ton tai"}, status=404)

        return JsonResponse(esp_to_dict(esp))

    def patch(self, request, hashcode):
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return JsonResponse({"message": "ESP khong ton tai"}, status=404)

        if "name" in body:
            esp.esp_name = body["name"]

        if "is_sensor" in body:
            if not isinstance(body["is_sensor"], bool):
                return JsonResponse({"message": "is_sensor phai la true hoac false"}, status=400)
            esp.is_sensor = body["is_sensor"]

        if "home_id" in body:
            if not HomeModel.objects.filter(id=body["home_id"]).exists():
                return JsonResponse({"message": "Nha khong ton tai"}, status=404)
            esp.home_id = body["home_id"]

            if esp.room_id and not RoomModel.objects.filter(id=esp.room_id, home_id=esp.home_id).exists():
                esp.room_id = None

        if "room_id" in body:
            room_id = body["room_id"]
            if room_id is None:
                esp.room_id = None
            else:
                if not RoomModel.objects.filter(id=room_id, home_id=esp.home_id).exists():
                    return JsonResponse({"message": "Phong khong thuoc nha nay"}, status=400)
                esp.room_id = room_id

        esp.save()
        return JsonResponse({"message": "Cap nhat ESP thanh cong", "data": esp_to_dict(esp)})

    def delete(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return JsonResponse({"message": "ESP khong ton tai"}, status=404)

        esp.delete()
        return JsonResponse({"message": "Xoa ESP thanh cong"})


@method_decorator(csrf_exempt, name="dispatch")
class ESPMQTTMessageView(View):
    def get(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return JsonResponse({"message": "ESP khong ton tai"}, status=404)

        messages = MQTTMessageModel.objects.filter(device=esp)
        return JsonResponse(
            [mqtt_message_to_dict(message) for message in messages],
            safe=False,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ESPSensorLatestView(View):
    def get(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return JsonResponse({"message": "ESP khong ton tai"}, status=404)

        reading = SensorReadingModel.objects.filter(device=esp).first()
        if reading is None:
            return JsonResponse({"message": "Chua co du lieu sensor"}, status=404)

        return JsonResponse(sensor_reading_to_dict(reading))


@method_decorator(csrf_exempt, name="dispatch")
class ESPSensorHistoryView(View):
    def get(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return JsonResponse({"message": "ESP khong ton tai"}, status=404)

        limit = int(request.GET.get("limit", 30))
        readings = SensorReadingModel.objects.filter(device=esp)[:limit]
        return JsonResponse([sensor_reading_to_dict(reading) for reading in readings], safe=False)


@method_decorator(csrf_exempt, name="dispatch")
class DebugMQTTInboundView(View):
    def post(self, request):
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        missing = missing_fields(body, ["topic", "payload"])
        if missing:
            return JsonResponse({"message": "Thieu du lieu", "missing_fields": missing}, status=400)

        if not isinstance(body["payload"], dict):
            return JsonResponse({"message": "payload phai la JSON object"}, status=400)

        try:
            mqtt_log = handle_inbound_message(body["topic"], json.dumps(body["payload"]))
        except Exception as exc:
            return JsonResponse({"message": "Xu ly MQTT inbound that bai", "error": str(exc)}, status=400)

        return JsonResponse(
            {
                "message": "Xu ly MQTT inbound thanh cong",
                "data": mqtt_message_to_dict(mqtt_log),
            },
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class SwitchView(View):
    def get(self, request, hashcode):
        try:
            esp = ESPModel.objects.get(hashcode=hashcode)
        except ESPModel.DoesNotExist:
            return JsonResponse({"message": "ESP khong ton tai"}, status=404)

        switches = SwitchModel.objects.filter(esp_device=esp)
        return JsonResponse([switch_to_dict(switch) for switch in switches], safe=False)


@method_decorator(csrf_exempt, name="dispatch")
class SwitchDetailView(View):
    def get(self, request, hashcode, switch_code):
        try:
            switch = SwitchModel.objects.get(switch_code=switch_code, esp_device__hashcode=hashcode)
        except SwitchModel.DoesNotExist:
            return JsonResponse({"message": "Switch khong ton tai"}, status=404)

        return JsonResponse(switch_to_dict(switch))

    def patch(self, request, hashcode, switch_code):
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        try:
            switch = SwitchModel.objects.get(switch_code=switch_code, esp_device__hashcode=hashcode)
        except SwitchModel.DoesNotExist:
            return JsonResponse({"message": "Switch khong ton tai"}, status=404)

        if set(body) != {"switch_name"}:
            return JsonResponse({"message": "Chi duoc phep cap nhat switch_name"}, status=400)

        switch.switch_name = body["switch_name"]
        switch.save(update_fields=["switch_name", "updated_at"])
        return JsonResponse({"message": "Cap nhat switch thanh cong", "data": switch_to_dict(switch)})


@method_decorator(csrf_exempt, name="dispatch")
class SwitchControlView(View):
    def post(self, request, hashcode, switch_code):
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"message": "Du lieu JSON khong hop le"}, status=400)

        if set(body) != {"state"}:
            return JsonResponse({"message": "Payload chi chap nhan field state"}, status=400)

        try:
            state = normalize_state(body["state"])
        except MQTTServiceError as exc:
            return JsonResponse({"message": str(exc)}, status=400)

        try:
            switch = SwitchModel.objects.select_related("esp_device").get(
                switch_code=switch_code,
                esp_device__hashcode=hashcode,
            )
        except SwitchModel.DoesNotExist:
            return JsonResponse({"message": "Switch khong ton tai"}, status=404)

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
            return JsonResponse(
                {
                    "message": "Publish MQTT that bai",
                    "data": command_to_dict(command),
                },
                status=502,
            )

        command.status = DeviceCommandModel.CommandStatus.PUBLISHED
        command.published_at = timezone.now()
        command.save(update_fields=["status", "published_at"])

        switch.desired_state = state
        switch.sync_status = SwitchModel.SyncStatus.PENDING
        switch.last_controlled_at = timezone.now()
        switch.save(update_fields=["desired_state", "sync_status", "last_controlled_at", "updated_at"])

        return JsonResponse(
            {
                "message": "Gui lenh dieu khien thanh cong",
                "data": {
                    "command": command_to_dict(command),
                    "switch": switch_to_dict(switch),
                    "mqtt": publish_result,
                },
            },
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class SwitchCommandView(View):
    def get(self, request, hashcode, switch_code):
        try:
            switch = SwitchModel.objects.get(
                switch_code=switch_code,
                esp_device__hashcode=hashcode,
            )
        except SwitchModel.DoesNotExist:
            return JsonResponse({"message": "Switch khong ton tai"}, status=404)

        commands = DeviceCommandModel.objects.filter(
            esp=switch.esp_device,
            switch=switch,
        )
        return JsonResponse([command_to_dict(command) for command in commands], safe=False)


api_homes = HomeView.as_view()
api_rooms = RoomView.as_view()
api_esps = ESPView.as_view()
