from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Alert
from .serializers import alert_to_dict
from automation.services import AutomationService


class AlertView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        alerts = Alert.objects.select_related("device", "sensor_reading").filter(device__home__owner=request.user)

        is_resolved = request.GET.get("is_resolved")
        severity = request.GET.get("severity")
        alert_type = request.GET.get("alert_type")
        hashcode = request.GET.get("hashcode")

        if is_resolved is not None:
            if is_resolved.lower() == "true":
                alerts = alerts.filter(is_resolved=True)
            elif is_resolved.lower() == "false":
                alerts = alerts.filter(is_resolved=False)
            else:
                return Response({"is_resolved": "is_resolved phai la true hoac false."}, status=status.HTTP_400_BAD_REQUEST)

        if severity:
            alerts = alerts.filter(severity=severity)
        if alert_type:
            alerts = alerts.filter(alert_type=alert_type)
        if hashcode:
            alerts = alerts.filter(device__hashcode=hashcode)

        try:
            limit = int(request.GET.get("limit", 50))
        except (TypeError, ValueError):
            return Response({"limit": "limit phai la so nguyen."}, status=status.HTTP_400_BAD_REQUEST)

        if limit <= 0:
            return Response({"limit": "limit phai lon hon 0."}, status=status.HTTP_400_BAD_REQUEST)

        return Response([alert_to_dict(alert) for alert in alerts[: min(limit, 100)]], status=status.HTTP_200_OK)


class AlertDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        alert = get_object_or_404(
            Alert.objects.select_related("device", "sensor_reading"),
            id=id,
            device__home__owner=request.user,
        )
        return Response(alert_to_dict(alert), status=status.HTTP_200_OK)


class AlertResolveView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        alert = get_object_or_404(Alert, id=id, device__home__owner=request.user)

        if alert.is_resolved:
            return Response(
                {"message": "Canh bao nay da duoc xu ly truoc do.", "alert": alert_to_dict(alert)},
                status=status.HTTP_200_OK,
            )

        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.save(update_fields=["is_resolved", "resolved_at"])
        AutomationService().handle_alert_resolved(alert)

        return Response(
            {"message": "Da xu ly canh bao thanh cong.", "alert": alert_to_dict(alert)},
            status=status.HTTP_200_OK,
        )
