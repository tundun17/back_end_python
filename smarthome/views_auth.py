from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import user_to_dict


User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        email = request.data.get("email", "")
        password = request.data.get("password")
        password_confirm = request.data.get("password_confirm")
        first_name = request.data.get("first_name", "")
        last_name = request.data.get("last_name", "")

        if not username:
            return Response({"username": "Vui long nhap username."}, status=status.HTTP_400_BAD_REQUEST)
        if not password:
            return Response({"password": "Vui long nhap password."}, status=status.HTTP_400_BAD_REQUEST)
        if password != password_confirm:
            return Response({"password_confirm": "Mat khau xac nhan khong khop."}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(username=username).exists():
            return Response({"username": "Username da ton tai."}, status=status.HTTP_400_BAD_REQUEST)
        if email and User.objects.filter(email=email).exists():
            return Response({"email": "Email da ton tai."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(password)
        except ValidationError as error:
            return Response({"password": list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        return Response(
            {"message": "Dang ky tai khoan thanh cong.", "user": user_to_dict(user)},
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {"message": "Dang xuat thanh cong. Client chi can xoa access token va refresh token."},
            status=status.HTTP_200_OK,
        )


class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(user_to_dict(request.user), status=status.HTTP_200_OK)

    def patch(self, request):
        user = request.user
        email = request.data.get("email", user.email)

        if email and User.objects.exclude(id=user.id).filter(email=email).exists():
            return Response({"email": "Email da duoc su dung boi tai khoan khac."}, status=status.HTTP_400_BAD_REQUEST)

        user.email = email
        user.first_name = request.data.get("first_name", user.first_name)
        user.last_name = request.data.get("last_name", user.last_name)
        user.save(update_fields=["email", "first_name", "last_name"])

        return Response(
            {"message": "Cap nhat thong tin thanh cong.", "user": user_to_dict(user)},
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        new_password_confirm = request.data.get("new_password_confirm")

        if not old_password:
            return Response({"old_password": "Vui long nhap mat khau cu."}, status=status.HTTP_400_BAD_REQUEST)
        if not new_password:
            return Response({"new_password": "Vui long nhap mat khau moi."}, status=status.HTTP_400_BAD_REQUEST)
        if new_password != new_password_confirm:
            return Response({"new_password_confirm": "Mat khau xac nhan khong khop."}, status=status.HTTP_400_BAD_REQUEST)
        if not request.user.check_password(old_password):
            return Response({"old_password": "Mat khau cu khong dung."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user=request.user)
        except ValidationError as error:
            return Response({"new_password": list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])
        return Response({"message": "Doi mat khau thanh cong."}, status=status.HTTP_200_OK)
