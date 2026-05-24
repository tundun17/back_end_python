import json

from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import ESP as ESPModel
from .models import Home as HomeModel
from .models import Room as RoomModel


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
class RoomView(View):
    def get(self, request, home_id):
        if not HomeModel.objects.filter(id=home_id).exists():
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

        if not HomeModel.objects.filter(id=home_id).exists():
            return JsonResponse({"message": "Nha khong ton tai"}, status=404)

        required_fields = ["name"]
        missing = missing_fields(body, required_fields)
        if missing:
            return JsonResponse(
                {"message": "Thieu du lieu", "missing_fields": missing},
                status=400,
            )

        if RoomModel.objects.filter(home_id=home_id, name=body["name"]).exists():
            return JsonResponse({"message": "Phong da ton tai trong nha nay"}, status=400)

        room = RoomModel.objects.create(
            home_id=home_id,
            name=body["name"],
            floor=body.get("floor", 1),
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
class ESPView(View):
    def get(self, request):
        esps = ESPModel.objects.select_related("home", "room").values(
            "id",
            "home_id",
            "room_id",
            "hashcode",
            "esp_name",
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
                    "status": esp.status,
                },
            },
            status=201,
        )


api_homes = HomeView.as_view()
api_rooms = RoomView.as_view()
api_esps = ESPView.as_view()
