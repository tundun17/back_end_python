from django.urls import path

from .views import (
    DebugMQTTInboundView,
    ESPDetailView,
    ESPMQTTMessageView,
    ESPSensorHistoryView,
    ESPSensorLatestView,
    ESPView,
    HomeDetailView,
    HomeOverviewView,
    HomeView,
    LoginView,
    LogoutView,
    RegisterView,
    RoomDetailView,
    RoomView,
    SwitchCommandView,
    SwitchControlView,
    SwitchDetailView,
    SwitchView,
    ChangePasswordView,
    UserMeView,
    index,
)


urlpatterns = [
    path("", index, name="smarthome_index"),
    path("auth/register/", RegisterView.as_view(), name="auth_register_views"),
    path("auth/login/", LoginView.as_view(), name="auth_login_views"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout_views"),
    path("users/me/", UserMeView.as_view(), name="user_me_views"),
    path("users/change-password/", ChangePasswordView.as_view(), name="user_change_password_views"),

    path("homes/", HomeView.as_view(), name="home_views"),
    path("homes/<int:home_id>/", HomeDetailView.as_view(), name="home_detail_views"),
    path("dashboard/homes/<int:home_id>/overview/", HomeOverviewView.as_view(), name="home_overview_views"),
    path("homes/<int:home_id>/rooms/", RoomView.as_view(), name="room_views"),
    path("homes/<int:home_id>/rooms/<int:room_id>/", RoomDetailView.as_view(), name="room_detail_views"),
    
    path("esps/", ESPView.as_view(), name="esp_views"),
    path("esps/<str:hashcode>/", ESPDetailView.as_view(), name="esp_detail_views"),
    path("esps/<str:hashcode>/mqtt-messages/", ESPMQTTMessageView.as_view(), name="esp_mqtt_message_views"),
    path("esps/<str:hashcode>/sensor-readings/latest/", ESPSensorLatestView.as_view(), name="esp_sensor_latest_views"),
    path("esps/<str:hashcode>/sensor-readings/history/", ESPSensorHistoryView.as_view(), name="esp_sensor_history_views"),
    path("esps/<str:hashcode>/switches/", SwitchView.as_view(), name="switch_views"),
    path("esps/<str:hashcode>/switches/<str:switch_code>/control/", SwitchControlView.as_view(), name="switch_control_views"),
    path("esps/<str:hashcode>/switches/<str:switch_code>/commands/", SwitchCommandView.as_view(), name="switch_command_views"),
    path("esps/<str:hashcode>/switches/<str:switch_code>/", SwitchDetailView.as_view(), name="switch_detail_views"),
    path("debug/mqtt/inbound/", DebugMQTTInboundView.as_view(), name="debug_mqtt_inbound_views"),
]
