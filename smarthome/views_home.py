from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Home, Room
from .serializers import home_overview_to_dict, home_to_dict, room_to_dict


class HomeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        homes = Home.objects.filter(owner=request.user)
        return Response([home_to_dict(home) for home in homes], status=status.HTTP_200_OK)

    def post(self, request):
        name = request.data.get("name")
        if not name:
            return Response({"name": "Vui long nhap ten nha."}, status=status.HTTP_400_BAD_REQUEST)

        home = Home.objects.create(
            owner=request.user,
            name=name,
            address=request.data.get("address", ""),
            description=request.data.get("description", ""),
        )
        return Response({"message": "Tao nha thanh cong.", "home": home_to_dict(home)}, status=status.HTTP_201_CREATED)


class HomeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_home(self, request, home_id):
        return get_object_or_404(Home, id=home_id, owner=request.user)

    def get(self, request, home_id):
        return Response(home_to_dict(self.get_home(request, home_id)), status=status.HTTP_200_OK)

    def patch(self, request, home_id):
        home = self.get_home(request, home_id)
        name = request.data.get("name", home.name)
        if not name:
            return Response({"name": "Ten nha khong duoc de trong."}, status=status.HTTP_400_BAD_REQUEST)

        home.name = name
        home.address = request.data.get("address", home.address)
        home.description = request.data.get("description", home.description)
        home.save(update_fields=["name", "address", "description", "updated_at"])
        return Response({"message": "Cap nhat nha thanh cong.", "home": home_to_dict(home)}, status=status.HTTP_200_OK)

    def delete(self, request, home_id):
        self.get_home(request, home_id).delete()
        return Response({"message": "Xoa nha thanh cong."}, status=status.HTTP_200_OK)


class HomeOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get_home(self, request, home_id):
        return get_object_or_404(Home, id=home_id, owner=request.user)

    def get(self, request, home_id):
        home = self.get_home(request, home_id)
        return Response(home_overview_to_dict(home), status=status.HTTP_200_OK)


class RoomView(APIView):
    permission_classes = [IsAuthenticated]

    def get_home(self, request, home_id):
        return get_object_or_404(Home, id=home_id, owner=request.user)

    def get(self, request, home_id):
        home = self.get_home(request, home_id)
        rooms = Room.objects.filter(home=home)
        return Response([room_to_dict(room) for room in rooms], status=status.HTTP_200_OK)

    def post(self, request, home_id):
        home = self.get_home(request, home_id)
        name = request.data.get("name")
        floor = request.data.get("floor", 1)

        if not name:
            return Response({"name": "Vui long nhap ten phong."}, status=status.HTTP_400_BAD_REQUEST)
        if Room.objects.filter(home=home, name=name).exists():
            return Response({"name": "Ten phong da ton tai trong nha nay."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            floor = int(floor)
        except (TypeError, ValueError):
            return Response({"floor": "Tang phai la so nguyen."}, status=status.HTTP_400_BAD_REQUEST)

        room = Room.objects.create(
            home=home,
            name=name,
            floor=floor,
            description=request.data.get("description", ""),
        )
        return Response({"message": "Tao phong thanh cong.", "room": room_to_dict(room)}, status=status.HTTP_201_CREATED)


class RoomDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_room(self, request, home_id, room_id):
        return get_object_or_404(Room, id=room_id, home_id=home_id, home__owner=request.user)

    def get(self, request, home_id, room_id):
        return Response(room_to_dict(self.get_room(request, home_id, room_id)), status=status.HTTP_200_OK)

    def patch(self, request, home_id, room_id):
        room = self.get_room(request, home_id, room_id)
        name = request.data.get("name", room.name)
        floor = request.data.get("floor", room.floor)

        if not name:
            return Response({"name": "Ten phong khong duoc de trong."}, status=status.HTTP_400_BAD_REQUEST)
        if Room.objects.exclude(id=room.id).filter(home=room.home, name=name).exists():
            return Response({"name": "Ten phong da ton tai trong nha nay."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            floor = int(floor)
        except (TypeError, ValueError):
            return Response({"floor": "Tang phai la so nguyen."}, status=status.HTTP_400_BAD_REQUEST)

        room.name = name
        room.floor = floor
        room.description = request.data.get("description", room.description)
        room.save(update_fields=["name", "floor", "description", "updated_at"])
        return Response({"message": "Cap nhat phong thanh cong.", "room": room_to_dict(room)}, status=status.HTTP_200_OK)

    def delete(self, request, home_id, room_id):
        self.get_room(request, home_id, room_id).delete()
        return Response({"message": "Xoa phong thanh cong."}, status=status.HTTP_200_OK)
