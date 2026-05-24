from django.urls import path

from .views import RegisterAPIView, UserMeAPIView, ChangePasswordAPIView, HomeListCreateAPIView, HomeDetailAPIView, RoomListCreateAPIView, RoomDetailAPIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    #Auth and User
    path("auth/register/", RegisterAPIView.as_view(), name="auth-register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("users/me/", UserMeAPIView.as_view(), name="users-me"),
    path("users/change-password/",ChangePasswordAPIView.as_view(), name="users-change-password",),
    
    # Home
    path("homes/", HomeListCreateAPIView.as_view(), name="home-list-create"),
    path("homes/<int:id>/", HomeDetailAPIView.as_view(), name="home-detail"),

    # Room
    path(
        "homes/<int:home_id>/rooms/",
        RoomListCreateAPIView.as_view(),
        name="room-list-create",
    ),
    path("rooms/<int:id>/", RoomDetailAPIView.as_view(), name="room-detail"),
]
