from django.urls import path

from .views import ESPView, HomeView, RoomView, index


urlpatterns = [
    path("", index, name="smarthome_index"),
    path("homes/", HomeView.as_view(), name="home_views"),
    path("homes/<int:home_id>/rooms/", RoomView.as_view(), name="room_views"),
    path("esps/", ESPView.as_view(), name="esp_views"),
]
