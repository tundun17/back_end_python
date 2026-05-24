from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404


from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Home, Room


User = get_user_model()
"""Các API liên quan đến người dùng"""
#Hàm lấy thông tin người dùng
def user_to_dict(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_joined": user.date_joined,
    }

# API đăng ký tài khoản mới
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        email = request.data.get("email", "")
        password = request.data.get("password")
        password_confirm = request.data.get("password_confirm")
        first_name = request.data.get("first_name", "")
        last_name = request.data.get("last_name", "")

        if not username:
            return Response(
                {"username": "Vui lòng nhập username."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password:
            return Response(
                {"password": "Vui lòng nhập password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if password != password_confirm:
            return Response(
                {"password_confirm": "Mật khẩu xác nhận không khớp."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"username": "Username đã tồn tại."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if email and User.objects.filter(email=email).exists():
            return Response(
                {"email": "Email đã tồn tại."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(password)
        except ValidationError as error:
            return Response(
                {"password": list(error.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        return Response(
            {
                "message": "Đăng ký tài khoản thành công.",
                "user": user_to_dict(user),
            },
            status=status.HTTP_201_CREATED,
        )

# API lấy thông tin user hiện tại và cập nhật thông tin
class UserMeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(user_to_dict(request.user), status=status.HTTP_200_OK)

    def patch(self, request):
        user = request.user

        email = request.data.get("email", user.email)
        first_name = request.data.get("first_name", user.first_name)
        last_name = request.data.get("last_name", user.last_name)

        if email and User.objects.exclude(id=user.id).filter(email=email).exists():
            return Response(
                {"email": "Email đã được sử dụng bởi tài khoản khác."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=["email", "first_name", "last_name"])

        return Response(
            {
                "message": "Cập nhật thông tin thành công.",
                "user": user_to_dict(user),
            },
            status=status.HTTP_200_OK,
        )

# API đổi mật khẩu 
class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        new_password_confirm = request.data.get("new_password_confirm")

        if not old_password:
            return Response(
                {"old_password": "Vui lòng nhập mật khẩu cũ."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not new_password:
            return Response(
                {"new_password": "Vui lòng nhập mật khẩu mới."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != new_password_confirm:
            return Response(
                {"new_password_confirm": "Mật khẩu xác nhận không khớp."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        if not user.check_password(old_password):
            return Response(
                {"old_password": "Mật khẩu cũ không đúng."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=user)
        except ValidationError as error:
            return Response(
                {"new_password": list(error.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        return Response(
            {"message": "Đổi mật khẩu thành công."},
            status=status.HTTP_200_OK,
        )
    
"""Các API liên quan đến Quản lý Home, Room"""
def home_to_dict(home):
    return {
        "id": home.id,
        "name": home.name,
        "address": home.address,
        "description": home.description,
        "created_at": home.created_at,
        "updated_at": home.updated_at,
    }

def room_to_dict(room):
    return {
        "id": room.id,
        "home_id": room.home_id,
        "home_name": room.home.name,
        "name": room.name,
        "floor": room.floor,
        "description": room.description,
        "created_at": room.created_at,
        "updated_at": room.updated_at,
    }

#API lấy danh sách nhà của người dùng và tạo nhà mới
class HomeListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        homes = Home.objects.filter(owner=request.user)
        data = [home_to_dict(home) for home in homes]

        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        name = request.data.get("name")
        address = request.data.get("address", "")
        description = request.data.get("description", "")

        if not name:
            return Response(
                {"name": "Vui lòng nhập tên nhà."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        home = Home.objects.create(
            owner=request.user,
            name=name,
            address=address,
            description=description,
        )

        return Response(
            {
                "message": "Tạo nhà thành công.",
                "home": home_to_dict(home),
            },
            status=status.HTTP_201_CREATED,
        )
    
#API lấy thông tin chi tiết của một nhà, cập nhật và xóa nhà
class HomeDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_home(self, request, id):
        return get_object_or_404(Home, id=id, owner=request.user)

    def get(self, request, id):
        home = self.get_home(request, id)
        return Response(home_to_dict(home), status=status.HTTP_200_OK)

    def patch(self, request, id):
        home = self.get_home(request, id)

        name = request.data.get("name", home.name)
        address = request.data.get("address", home.address)
        description = request.data.get("description", home.description)

        if not name:
            return Response(
                {"name": "Tên nhà không được để trống."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        home.name = name
        home.address = address
        home.description = description
        home.save(update_fields=["name", "address", "description", "updated_at"])

        return Response(
            {
                "message": "Cập nhật nhà thành công.",
                "home": home_to_dict(home),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id):
        home = self.get_home(request, id)
        home.delete()

        return Response(
            {"message": "Xóa nhà thành công."},
            status=status.HTTP_200_OK,
        )
    
#API lấy danh sách phòng trong một nhà và tạo phòng mới
class RoomListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_home(self, request, home_id):
        return get_object_or_404(Home, id=home_id, owner=request.user)

    def get(self, request, home_id):
        home = self.get_home(request, home_id)
        rooms = Room.objects.filter(home=home)

        data = [room_to_dict(room) for room in rooms]

        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, home_id):
        home = self.get_home(request, home_id)

        name = request.data.get("name")
        floor = request.data.get("floor", 1)
        description = request.data.get("description", "")

        if not name:
            return Response(
                {"name": "Vui lòng nhập tên phòng."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Room.objects.filter(home=home, name=name).exists():
            return Response(
                {"name": "Tên phòng đã tồn tại trong nhà này."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            floor = int(floor)
        except ValueError:
            return Response(
                {"floor": "Tầng phải là số nguyên."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        room = Room.objects.create(
            home=home,
            name=name,
            floor=floor,
            description=description,
        )

        return Response(
            {
                "message": "Tạo phòng thành công.",
                "room": room_to_dict(room),
            },
            status=status.HTTP_201_CREATED,
        )

#API lấy thông tin chi tiết của một phòng, cập nhật và xóa phòng 
class RoomDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_room(self, request, id):
        return get_object_or_404(Room, id=id, home__owner=request.user)

    def patch(self, request, id):
        room = self.get_room(request, id)

        name = request.data.get("name", room.name)
        floor = request.data.get("floor", room.floor)
        description = request.data.get("description", room.description)

        if not name:
            return Response(
                {"name": "Tên phòng không được để trống."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Room.objects.exclude(id=room.id).filter(
            home=room.home,
            name=name,
        ).exists():
            return Response(
                {"name": "Tên phòng đã tồn tại trong nhà này."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            floor = int(floor)
        except ValueError:
            return Response(
                {"floor": "Tầng phải là số nguyên."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        room.name = name
        room.floor = floor
        room.description = description
        room.save(update_fields=["name", "floor", "description", "updated_at"])

        return Response(
            {
                "message": "Cập nhật phòng thành công.",
                "room": room_to_dict(room),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id):
        room = self.get_room(request, id)
        room.delete()

        return Response(
            {"message": "Xóa phòng thành công."},
            status=status.HTTP_200_OK,
        )

