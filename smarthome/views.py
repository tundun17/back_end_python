from .views_alert import AlertDetailView, AlertResolveView, AlertView
from .views_auth import ChangePasswordView, LogoutView, RegisterView, UserMeView
from .views_automation import AutomationDetailView, AutomationView
from .views_esp import (
    ESPDetailView,
    ESPMQTTMessageView,
    ESPSensorHistoryView,
    ESPSensorLatestView,
    ESPView,
)
from .views_home import HomeDetailView, HomeOverviewView, HomeView, RoomDetailView, RoomView
from .views_switch import SwitchCommandView, SwitchControlView, SwitchDetailView, SwitchView


__all__ = [
    "AlertDetailView",
    "AlertResolveView",
    "AlertView",
    "AutomationDetailView",
    "AutomationView",
    "ChangePasswordView",
    "ESPDetailView",
    "ESPMQTTMessageView",
    "ESPSensorHistoryView",
    "ESPSensorLatestView",
    "ESPView",
    "HomeDetailView",
    "HomeOverviewView",
    "HomeView",
    "LogoutView",
    "RegisterView",
    "RoomDetailView",
    "RoomView",
    "SwitchCommandView",
    "SwitchControlView",
    "SwitchDetailView",
    "SwitchView",
    "UserMeView",
]
