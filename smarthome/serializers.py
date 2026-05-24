from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import ESP, Home, Room


def get_request_owner(request):
    if request and request.user.is_authenticated:
        return request.user

    User = get_user_model()
    user, _ = User.objects.get_or_create(username="demo_user")
    return user


class HomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Home
        fields = ["id", "name", "address", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "home", "name", "floor", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "home", "created_at", "updated_at"]


class ESPSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="esp_name")
    home_id = serializers.PrimaryKeyRelatedField(
        queryset=Home.objects.all(),
        source="home",
        write_only=True,
    )
    room_id = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.all(),
        source="room",
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ESP
        fields = [
            "id",
            "home_id",
            "room_id",
            "hashcode",
            "name",
            "status",
            "ip_address",
            "firmware_version",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "ip_address",
            "firmware_version",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        home = attrs.get("home")
        room = attrs.get("room")

        if room is not None and room.home_id != home.id:
            raise serializers.ValidationError(
                {"room_id": "room_id phai thuoc dung home_id"}
            )

        return attrs
