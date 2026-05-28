import json

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mqtt_client.client import MQTTClientError
from mqtt_client.handlers import handle_inbound_message
from mqtt_client.services import (
    MQTTServiceError,
    normalize_state,
    publish_control_command,
)

from .models import (
    Alert,
    DeviceCommand,
    ESP,
    Home,
    MQTTMessage,
    Room,
    SensorReading,
    Switch,
)


User = get_user_model()


# Trang kiểm tra app smarthome
def index(request):
    return HttpResponse("Xin chào. <br>Bạn đã đến trang Smart Home Backend")


# =========================
# Hàm tiện ích dùng chung
# =========================

def missing_fields(body, required_fields):
    return [field for field in required_fields if field not in body]


def parse_boolean(value, default=False):
    """
    Chuyển dữ liệu client gửi lên thành True/False.
    Hỗ trợ cả boolean thật và chuỗi: true, false, 1, 0, yes, no.
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value = value.strip().lower()

        if value in ["true", "1", "yes"]:
            return True

        if value in ["false", "0", "no"]:
            return False

    return default


def get_topic_hashcode(topic):
    """
    Lấy hashcode từ topic MQTT.
    Ví dụ:
    ESP_ABC123/sensor -> ESP_ABC123
    ESP_ABC123/state  -> ESP_ABC123
    """
    if not topic:
        return ""

    if topic == "syn":
        return ""

    return topic.split("/", 1)[0]


# =========================
# Convert object sang dict
# =========================

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
        "home_name": room.home.name,
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
        "hashcode": switch.esp_device.hashcode,
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
        "hashcode": command.esp.hashcode,
        "switch_id": command.switch_id,
        "switch_code": command.switch.switch_code if command.switch else None,
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
        "hashcode": message.device.hashcode if message.device else None,
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
        "hashcode": reading.device.hashcode,
        "temperature": reading.temperature,
        "humidity": reading.humidity,
        "gas": reading.gas,
        "recorded_at": reading.recorded_at,
        "created_at": reading.created_at,
    }

def alert_to_dict(alert):
    return {
        "id": alert.id,
        "device_id": alert.device_id,
        "hashcode": alert.device.hashcode,
        "sensor_reading_id": alert.sensor_reading_id,
        "alert_type": alert.alert_type,
        "alert_type_display": alert.get_alert_type_display(),
        "severity": alert.severity,
        "severity_display": alert.get_severity_display(),
        "message": alert.message,
        "threshold_value": alert.threshold_value,
        "actual_value": alert.actual_value,
        "is_resolved": alert.is_resolved,
        "created_at": alert.created_at,
        "resolved_at": alert.resolved_at,
    }

def home_overview_to_dict(home):
    esps = ESP.objects.filter(home=home)
    switches = Switch.objects.filter(esp_device__home=home)
    alerts = Alert.objects.filter(device__home=home)

    return {
        "home": {
            "id": home.id,
            "name": home.name,
            "address": home.address,
        },
        "rooms": {
            "total": Room.objects.filter(home=home).count(),
        },
        "esps": {
            "total": esps.count(),
            "online": esps.filter(status=ESP.Status.ONLINE).count(),
            "offline": esps.filter(status=ESP.Status.OFFLINE).count(),
            "unclaimed": esps.filter(status=ESP.Status.UNCLAIMED).count(),
            "error": esps.filter(status=ESP.Status.ERROR).count(),
            "sensors": esps.filter(is_sensor=True).count(),
            "controllers": esps.filter(is_sensor=False).count(),
        },
        "switches": {
            "total": switches.count(),
            "on": switches.filter(actual_state=Switch.State.ON).count(),
            "off": switches.filter(actual_state=Switch.State.OFF).count(),
            "pending": switches.filter(sync_status=Switch.SyncStatus.PENDING).count(),
            "failed": switches.filter(sync_status=Switch.SyncStatus.FAILED).count(),
            "synced": switches.filter(sync_status=Switch.SyncStatus.SYNCED).count(),
        },
        "alerts": {
            "total": alerts.count(),
            "unresolved": alerts.filter(is_resolved=False).count(),
            "resolved": alerts.filter(is_resolved=True).count(),
            "critical": alerts.filter(
                severity=Alert.Severity.CRITICAL,
                is_resolved=False,
            ).count(),
            "high": alerts.filter(
                severity=Alert.Severity.HIGH,
                is_resolved=False,
            ).count(),
        },
        "updated_at": timezone.now(),
    }


# =========================
# Auth và User API
# =========================

# API đăng ký tài khoản mới
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        email = request.data.get("email", "")
        password = request.data.get("password")
        password_confirm = request.data.get("password_confirm")
        first_name = request.data.get("first_name", "")
        last_name = request.data.get("last_name", "")

        if not username:
            return Response(
                {"username": "Vui lòng nhập username."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password:
            return Response(
                {"password": "Vui lòng nhập password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if password != password_confirm:
            return Response(
                {"password_confirm": "Mật khẩu xác nhận không khớp."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"username": "Username đã tồn tại."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if email and User.objects.filter(email=email).exists():
            return Response(
                {"email": "Email đã tồn tại."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(password)
        except ValidationError as error:
            return Response(
                {"password": list(error.messages)},
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
            {
                "message": "Đăng ký tài khoản thành công.",
                "user": user_to_dict(user),
            },
            status=status.HTTP_201_CREATED,
        )


# API logout JWT
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {
                "message": (
                    "Đăng xuất thành công. "
                    "Với JWT, client chỉ cần xóa access token và refresh token."
                )
            },
            status=status.HTTP_200_OK,
        )


# API lấy thông tin user hiện tại và cập nhật thông tin
class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(user_to_dict(request.user), status=status.HTTP_200_OK)

    def patch(self, request):
        user = request.user

        email = request.data.get("email", user.email)
        first_name = request.data.get("first_name", user.first_name)
        last_name = request.data.get("last_name", user.last_name)

        if email and User.objects.exclude(id=user.id).filter(email=email).exists():
            return Response(
                {"email": "Email đã được sử dụng bởi tài khoản khác."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=["email", "first_name", "last_name"])

        return Response(
            {
                "message": "Cập nhật thông tin thành công.",
                "user": user_to_dict(user),
            },
            status=status.HTTP_200_OK,
        )


# API đổi mật khẩu
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        new_password_confirm = request.data.get("new_password_confirm")

        if not old_password:
            return Response(
                {"old_password": "Vui lòng nhập mật khẩu cũ."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not new_password:
            return Response(
                {"new_password": "Vui lòng nhập mật khẩu mới."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != new_password_confirm:
            return Response(
                {"new_password_confirm": "Mật khẩu xác nhận không khớp."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        if not user.check_password(old_password):
            return Response(
                {"old_password": "Mật khẩu cũ không đúng."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=user)
        except ValidationError as error:
            return Response(
                {"new_password": list(error.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        return Response(
            {"message": "Đổi mật khẩu thành công."},
            status=status.HTTP_200_OK,
        )


# =========================
# Home API
# =========================

# API lấy danh sách nhà của user và tạo nhà mới
class HomeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        homes = Home.objects.filter(owner=request.user)
        data = [home_to_dict(home) for home in homes]

        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        name = request.data.get("name")
        address = request.data.get("address", "")
        description = request.data.get("description", "")

        if not name:
            return Response(
                {"name": "Vui lòng nhập tên nhà."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        home = Home.objects.create(
            owner=request.user,
            name=name,
            address=address,
            description=description,
        )

        return Response(
            {
                "message": "Tạo nhà thành công.",
                "home": home_to_dict(home),
            },
            status=status.HTTP_201_CREATED,
        )


# API lấy chi tiết, cập nhật và xóa nhà
class HomeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_home(self, request, home_id):
        return get_object_or_404(Home, id=home_id, owner=request.user)

    def get(self, request, home_id):
        home = self.get_home(request, home_id)

        return Response(home_to_dict(home), status=status.HTTP_200_OK)

    def patch(self, request, home_id):
        home = self.get_home(request, home_id)

        name = request.data.get("name", home.name)
        address = request.data.get("address", home.address)
        description = request.data.get("description", home.description)

        if not name:
            return Response(
                {"name": "Tên nhà không được để trống."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        home.name = name
        home.address = address
        home.description = description
        home.save(update_fields=["name", "address", "description", "updated_at"])

        return Response(
            {
                "message": "Cập nhật nhà thành công.",
                "home": home_to_dict(home),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, home_id):
        home = self.get_home(request, home_id)
        home.delete()

        return Response(
            {"message": "Xóa nhà thành công."},
            status=status.HTTP_200_OK,
        )


# API tổng quan dashboard theo nhà
class HomeOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get_home(self, request, home_id):
        return get_object_or_404(Home, id=home_id, owner=request.user)

    def get(self, request, home_id):
        home = self.get_home(request, home_id)

        return Response(home_overview_to_dict(home), status=status.HTTP_200_OK)


# =========================
# Room API
# =========================

# API lấy danh sách phòng trong một nhà và tạo phòng mới
class RoomView(APIView):
    permission_classes = [IsAuthenticated]

    def get_home(self, request, home_id):
        return get_object_or_404(Home, id=home_id, owner=request.user)

    def get(self, request, home_id):
        home = self.get_home(request, home_id)
        rooms = Room.objects.filter(home=home)

        data = [room_to_dict(room) for room in rooms]

        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, home_id):
        home = self.get_home(request, home_id)

        name = request.data.get("name")
        floor = request.data.get("floor", 1)
        description = request.data.get("description", "")

        if not name:
            return Response(
                {"name": "Vui lòng nhập tên phòng."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Room.objects.filter(home=home, name=name).exists():
            return Response(
                {"name": "Tên phòng đã tồn tại trong nhà này."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            floor = int(floor)
        except (TypeError, ValueError):
            return Response(
                {"floor": "Tầng phải là số nguyên."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        room = Room.objects.create(
            home=home,
            name=name,
            floor=floor,
            description=description,
        )

        return Response(
            {
                "message": "Tạo phòng thành công.",
                "room": room_to_dict(room),
            },
            status=status.HTTP_201_CREATED,
        )


# API lấy chi tiết, cập nhật và xóa phòng
class RoomDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_room(self, request, home_id, room_id):
        return get_object_or_404(
            Room,
            id=room_id,
            home_id=home_id,
            home__owner=request.user,
        )

    def get(self, request, home_id, room_id):
        room = self.get_room(request, home_id, room_id)

        return Response(room_to_dict(room), status=status.HTTP_200_OK)

    def patch(self, request, home_id, room_id):
        room = self.get_room(request, home_id, room_id)

        name = request.data.get("name", room.name)
        floor = request.data.get("floor", room.floor)
        description = request.data.get("description", room.description)

        if not name:
            return Response(
                {"name": "Tên phòng không được để trống."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Room.objects.exclude(id=room.id).filter(
            home=room.home,
            name=name,
        ).exists():
            return Response(
                {"name": "Tên phòng đã tồn tại trong nhà này."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            floor = int(floor)
        except (TypeError, ValueError):
            return Response(
                {"floor": "Tầng phải là số nguyên."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        room.name = name
        room.floor = floor
        room.description = description
        room.save(update_fields=["name", "floor", "description", "updated_at"])

        return Response(
            {
                "message": "Cập nhật phòng thành công.",
                "room": room_to_dict(room),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, home_id, room_id):
        room = self.get_room(request, home_id, room_id)
        room.delete()

        return Response(
            {"message": "Xóa phòng thành công."},
            status=status.HTTP_200_OK,
        )


# =========================
# ESP API
# =========================

# API lấy danh sách ESP và tạo ESP mới
class ESPView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        esps = ESP.objects.filter(home__owner=request.user).select_related(
            "home",
            "room",
        )

        data = [esp_to_dict(esp) for esp in esps]

        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        home_id = request.data.get("home_id")
        room_id = request.data.get("room_id")
        hashcode = request.data.get("hashcode")
        name = request.data.get("name")
        is_sensor = parse_boolean(request.data.get("is_sensor"), False)

        if not home_id:
            return Response(
                {"home_id": "Vui lòng nhập home_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not hashcode:
            return Response(
                {"hashcode": "Vui lòng nhập hashcode."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not name:
            return Response(
                {"name": "Vui lòng nhập tên ESP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        home = get_object_or_404(Home, id=home_id, owner=request.user)

        room = None
        if room_id is not None:
            room = get_object_or_404(
                Room,
                id=room_id,
                home=home,
                home__owner=request.user,
            )

        if ESP.objects.filter(hashcode=hashcode).exists():
            return Response(
                {"hashcode": "Hashcode ESP đã tồn tại."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        esp = ESP.objects.create(
            home=home,
            room=room,
            hashcode=hashcode,
            esp_name=name,
            is_sensor=is_sensor,
        )

        return Response(
            {
                "message": "Tạo ESP thành công.",
                "esp": esp_to_dict(esp),
            },
            status=status.HTTP_201_CREATED,
        )


# API lấy chi tiết, cập nhật và xóa ESP
class ESPDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_esp(self, request, hashcode):
        return get_object_or_404(
            ESP,
            hashcode=hashcode,
            home__owner=request.user,
        )

    def get(self, request, hashcode):
        esp = self.get_esp(request, hashcode)

        return Response(esp_to_dict(esp), status=status.HTTP_200_OK)

    def patch(self, request, hashcode):
        esp = self.get_esp(request, hashcode)

        if "name" in request.data:
            if not request.data["name"]:
                return Response(
                    {"name": "Tên ESP không được để trống."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            esp.esp_name = request.data["name"]

        if "is_sensor" in request.data:
            esp.is_sensor = parse_boolean(request.data.get("is_sensor"), esp.is_sensor)

        if "home_id" in request.data:
            home = get_object_or_404(
                Home,
                id=request.data["home_id"],
                owner=request.user,
            )
            esp.home = home

            if esp.room and esp.room.home_id != home.id:
                esp.room = None

        if "room_id" in request.data:
            room_id = request.data.get("room_id")

            if room_id is None:
                esp.room = None
            else:
                room = get_object_or_404(
                    Room,
                    id=room_id,
                    home=esp.home,
                    home__owner=request.user,
                )
                esp.room = room

        esp.save()

        return Response(
            {
                "message": "Cập nhật ESP thành công.",
                "esp": esp_to_dict(esp),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, hashcode):
        esp = self.get_esp(request, hashcode)
        esp.delete()

        return Response(
            {"message": "Xóa ESP thành công."},
            status=status.HTTP_200_OK,
        )


# API lấy MQTT message của ESP
class ESPMQTTMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def get_esp(self, request, hashcode):
        return get_object_or_404(
            ESP,
            hashcode=hashcode,
            home__owner=request.user,
        )

    def get(self, request, hashcode):
        esp = self.get_esp(request, hashcode)
        messages = MQTTMessage.objects.filter(device=esp)

        data = [mqtt_message_to_dict(message) for message in messages]

        return Response(data, status=status.HTTP_200_OK)


# API lấy sensor reading mới nhất của ESP
class ESPSensorLatestView(APIView):
    permission_classes = [IsAuthenticated]

    def get_esp(self, request, hashcode):
        return get_object_or_404(
            ESP,
            hashcode=hashcode,
            home__owner=request.user,
        )

    def get(self, request, hashcode):
        esp = self.get_esp(request, hashcode)

        reading = SensorReading.objects.filter(device=esp).first()

        if reading is None:
            return Response(
                {"message": "Chưa có dữ liệu cảm biến."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(sensor_reading_to_dict(reading), status=status.HTTP_200_OK)


# API lấy lịch sử sensor reading của ESP
class ESPSensorHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get_esp(self, request, hashcode):
        return get_object_or_404(
            ESP,
            hashcode=hashcode,
            home__owner=request.user,
        )

    def get(self, request, hashcode):
        esp = self.get_esp(request, hashcode)

        try:
            limit = int(request.GET.get("limit", 30))
        except (TypeError, ValueError):
            return Response(
                {"limit": "limit phải là số nguyên."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if limit <= 0:
            return Response(
                {"limit": "limit phải lớn hơn 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if limit > 100:
            limit = 100

        readings = SensorReading.objects.filter(device=esp)[:limit]
        data = [sensor_reading_to_dict(reading) for reading in readings]

        return Response(data, status=status.HTTP_200_OK)


# =========================
# Switch API
# =========================

# API lấy danh sách switch của ESP
class SwitchView(APIView):
    permission_classes = [IsAuthenticated]

    def get_esp(self, request, hashcode):
        return get_object_or_404(
            ESP,
            hashcode=hashcode,
            home__owner=request.user,
        )

    def get(self, request, hashcode):
        esp = self.get_esp(request, hashcode)
        switches = Switch.objects.filter(esp_device=esp)

        data = [switch_to_dict(switch) for switch in switches]

        return Response(data, status=status.HTTP_200_OK)


# API lấy chi tiết và cập nhật switch
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
        switch = self.get_switch(request, hashcode, switch_code)

        return Response(switch_to_dict(switch), status=status.HTTP_200_OK)

    def patch(self, request, hashcode, switch_code):
        switch = self.get_switch(request, hashcode, switch_code)

        if "switch_name" not in request.data:
            return Response(
                {"switch_name": "Vui lòng nhập switch_name."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        switch.switch_name = request.data.get("switch_name", "")
        switch.save(update_fields=["switch_name", "updated_at"])

        return Response(
            {
                "message": "Cập nhật switch thành công.",
                "switch": switch_to_dict(switch),
            },
            status=status.HTTP_200_OK,
        )


# API gửi lệnh điều khiển switch qua MQTT
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
            return Response(
                {"state": "Vui lòng nhập state."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            state = normalize_state(state_input)
        except MQTTServiceError as error:
            return Response(
                {"state": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        switch = self.get_switch(request, hashcode, switch_code)

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
                {
                    "message": "Publish MQTT thất bại.",
                    "command": command_to_dict(command),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

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

        return Response(
            {
                "message": "Gửi lệnh điều khiển thành công.",
                "command": command_to_dict(command),
                "switch": switch_to_dict(switch),
                "mqtt": publish_result,
            },
            status=status.HTTP_201_CREATED,
        )


# API lấy lịch sử command của switch
class SwitchCommandView(APIView):
    permission_classes = [IsAuthenticated]

    def get_switch(self, request, hashcode, switch_code):
        return get_object_or_404(
            Switch,
            switch_code=switch_code,
            esp_device__hashcode=hashcode,
            esp_device__home__owner=request.user,
        )

    def get(self, request, hashcode, switch_code):
        switch = self.get_switch(request, hashcode, switch_code)

        commands = DeviceCommand.objects.filter(
            esp=switch.esp_device,
            switch=switch,
        )

        data = [command_to_dict(command) for command in commands]

        return Response(data, status=status.HTTP_200_OK)


# =========================
# Debug MQTT API
# =========================

# API giả lập MQTT inbound để test handler bằng Postman
class DebugMQTTInboundView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        
        topic = request.data.get("topic")
        payload = request.data.get("payload")

        if not topic:
            return Response(
                {"topic": "Vui lòng nhập topic."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payload is None:
            return Response(
                {"payload": "Vui lòng nhập payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(payload, dict):
            return Response(
                {"payload": "payload phải là JSON object."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        hashcode = payload.get("hashcode") or get_topic_hashcode(topic)

        if hashcode:
            if not ESP.objects.filter(
                hashcode=hashcode,
                home__owner=request.user,
            ).exists():
                return Response(
                    {"message": "ESP không tồn tại hoặc không thuộc user hiện tại."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            mqtt_log = handle_inbound_message(topic, json.dumps(payload))
        except Exception as error:
            return Response(
                {
                    "message": "Xử lý MQTT inbound thất bại.",
                    "error": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Xử lý MQTT inbound thành công.",
                "mqtt_message": mqtt_message_to_dict(mqtt_log),
            },
            status=status.HTTP_201_CREATED,
        )
    
# =========================
# Alert API
# =========================

# API lấy danh sách cảnh báo của user hiện tại
class AlertView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        alerts = Alert.objects.select_related(
            "device",
            "sensor_reading",
        ).filter(
            device__home__owner=request.user
        )

        is_resolved = request.GET.get("is_resolved")
        severity = request.GET.get("severity")
        alert_type = request.GET.get("alert_type")
        hashcode = request.GET.get("hashcode")

        if is_resolved is not None:
            if is_resolved.lower() == "true":
                alerts = alerts.filter(is_resolved=True)
            elif is_resolved.lower() == "false":
                alerts = alerts.filter(is_resolved=False)
            else:
                return Response(
                    {"is_resolved": "is_resolved phải là true hoặc false."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if severity:
            alerts = alerts.filter(severity=severity)

        if alert_type:
            alerts = alerts.filter(alert_type=alert_type)

        if hashcode:
            alerts = alerts.filter(device__hashcode=hashcode)

        try:
            limit = int(request.GET.get("limit", 50))
        except (TypeError, ValueError):
            return Response(
                {"limit": "limit phải là số nguyên."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if limit <= 0:
            return Response(
                {"limit": "limit phải lớn hơn 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if limit > 100:
            limit = 100

        data = [alert_to_dict(alert) for alert in alerts[:limit]]

        return Response(data, status=status.HTTP_200_OK)
    
# API xem chi tiết một cảnh báo
class AlertDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_alert(self, request, id):
        return get_object_or_404(
            Alert.objects.select_related("device", "sensor_reading"),
            id=id,
            device__home__owner=request.user,
        )

    def get(self, request, id):
        alert = self.get_alert(request, id)

        return Response(alert_to_dict(alert), status=status.HTTP_200_OK)

# API đánh dấu cảnh báo đã xử lý
class AlertResolveView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        alert = get_object_or_404(
            Alert,
            id=id,
            device__home__owner=request.user,
        )

        if alert.is_resolved:
            return Response(
                {
                    "message": "Cảnh báo này đã được xử lý trước đó.",
                    "alert": alert_to_dict(alert),
                },
                status=status.HTTP_200_OK,
            )

        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.save(update_fields=["is_resolved", "resolved_at"])

        return Response(
            {
                "message": "Đã xử lý cảnh báo thành công.",
                "alert": alert_to_dict(alert),
            },
            status=status.HTTP_200_OK,
        )