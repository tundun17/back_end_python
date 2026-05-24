from django.urls import path

from .views import ESPListCreateAPIView, HomeListCreateAPIView, RoomListCreateAPIView


urlpatterns = [
    path("homes/", HomeListCreateAPIView.as_view(), name="home-list-create"),
    path("homes/<int:home_id>/rooms/", RoomListCreateAPIView.as_view(), name="room-list-create"),
    path("esps/", ESPListCreateAPIView.as_view(), name="esp-list-create"),
]
