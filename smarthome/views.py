from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ESP, Home, Room
from .serializers import ESPSerializer, HomeSerializer, RoomSerializer, get_request_owner


class HomeListCreateAPIView(APIView):
    def get(self, request):
        owner = get_request_owner(request)
        homes = Home.objects.filter(owner=owner)
        serializer = HomeSerializer(homes, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = HomeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        home = serializer.save(owner=get_request_owner(request))
        return Response(HomeSerializer(home).data, status=status.HTTP_201_CREATED)


class RoomListCreateAPIView(APIView):
    def get_home(self, home_id):
        return get_object_or_404(Home, id=home_id)

    def get(self, request, home_id):
        home = self.get_home(home_id)
        rooms = Room.objects.filter(home=home)
        serializer = RoomSerializer(rooms, many=True)
        return Response(serializer.data)

    def post(self, request, home_id):
        home = self.get_home(home_id)
        serializer = RoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        room = serializer.save(home=home)
        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


class ESPListCreateAPIView(APIView):
    def get(self, request):
        esps = ESP.objects.select_related("home", "room").all()
        serializer = ESPSerializer(esps, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ESPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        esp = serializer.save()
        return Response(ESPSerializer(esp).data, status=status.HTTP_201_CREATED)
