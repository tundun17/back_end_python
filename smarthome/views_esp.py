from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ESP, Home, MQTTMessage, Room, SensorReading
from .serializers import (
    esp_to_dict,
    mqtt_message_to_dict,
    parse_boolean,
    sensor_reading_to_dict,
)


class ESPView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        esps = ESP.objects.filter(home__owner=request.user).select_related("home", "room")
        return Response([esp_to_dict(esp) for esp in esps], status=status.HTTP_200_OK)

    def post(self, request):
        home_id = request.data.get("home_id")
        room_id = request.data.get("room_id")
        hashcode = request.data.get("hashcode")
        name = request.data.get("name")
        is_sensor = parse_boolean(request.data.get("is_sensor"), False)

        if not home_id:
            return Response({"home_id": "Vui long nhap home_id."}, status=status.HTTP_400_BAD_REQUEST)
        if not hashcode:
            return Response({"hashcode": "Vui long nhap hashcode."}, status=status.HTTP_400_BAD_REQUEST)
        if not name:
            return Response({"name": "Vui long nhap ten ESP."}, status=status.HTTP_400_BAD_REQUEST)

        home = get_object_or_404(Home, id=home_id, owner=request.user)
        room = None
        if room_id is not None:
            room = get_object_or_404(Room, id=room_id, home=home)

        if ESP.objects.filter(hashcode=hashcode).exists():
            return Response({"hashcode": "Hashcode ESP da ton tai."}, status=status.HTTP_400_BAD_REQUEST)

        esp = ESP.objects.create(home=home, room=room, hashcode=hashcode, esp_name=name, is_sensor=is_sensor)
        return Response({"message": "Tao ESP thanh cong.", "esp": esp_to_dict(esp)}, status=status.HTTP_201_CREATED)


class ESPDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_esp(self, request, hashcode):
        return get_object_or_404(ESP, hashcode=hashcode, home__owner=request.user)

    def get(self, request, hashcode):
        return Response(esp_to_dict(self.get_esp(request, hashcode)), status=status.HTTP_200_OK)

    def patch(self, request, hashcode):
        esp = self.get_esp(request, hashcode)

        if "name" in request.data:
            if not request.data["name"]:
                return Response({"name": "Ten ESP khong duoc de trong."}, status=status.HTTP_400_BAD_REQUEST)
            esp.esp_name = request.data["name"]

        if "is_sensor" in request.data:
            esp.is_sensor = parse_boolean(request.data.get("is_sensor"), esp.is_sensor)

        if "home_id" in request.data:
            home = get_object_or_404(Home, id=request.data["home_id"], owner=request.user)
            esp.home = home
            if esp.room and esp.room.home_id != home.id:
                esp.room = None

        if "room_id" in request.data:
            room_id = request.data.get("room_id")
            esp.room = None if room_id is None else get_object_or_404(Room, id=room_id, home=esp.home)

        esp.save()
        return Response({"message": "Cap nhat ESP thanh cong.", "esp": esp_to_dict(esp)}, status=status.HTTP_200_OK)

    def delete(self, request, hashcode):
        self.get_esp(request, hashcode).delete()
        return Response({"message": "Xoa ESP thanh cong."}, status=status.HTTP_200_OK)


class ESPMQTTMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, hashcode):
        esp = get_object_or_404(ESP, hashcode=hashcode, home__owner=request.user)
        messages = MQTTMessage.objects.filter(device=esp)
        return Response([mqtt_message_to_dict(message) for message in messages], status=status.HTTP_200_OK)


class ESPSensorLatestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, hashcode):
        esp = get_object_or_404(ESP, hashcode=hashcode, home__owner=request.user)
        reading = SensorReading.objects.filter(device=esp).first()
        if reading is None:
            return Response({"message": "Chua co du lieu cam bien."}, status=status.HTTP_404_NOT_FOUND)
        return Response(sensor_reading_to_dict(reading), status=status.HTTP_200_OK)


class ESPSensorHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, hashcode):
        esp = get_object_or_404(ESP, hashcode=hashcode, home__owner=request.user)
        try:
            limit = int(request.GET.get("limit", 30))
        except (TypeError, ValueError):
            return Response({"limit": "limit phai la so nguyen."}, status=status.HTTP_400_BAD_REQUEST)
        if limit <= 0:
            return Response({"limit": "limit phai lon hon 0."}, status=status.HTTP_400_BAD_REQUEST)
        readings = SensorReading.objects.filter(device=esp)[: min(limit, 100)]
        return Response([sensor_reading_to_dict(reading) for reading in readings], status=status.HTTP_200_OK)
