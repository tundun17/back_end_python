import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("smarthome", "0004_switch_and_mqttmessage_alignment"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="esp",
            name="api_key",
        ),
        migrations.AddField(
            model_name="esp",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="room",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="switch",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="switch",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="alert",
            name="alert_type",
            field=models.CharField(
                choices=[
                    ("HIGH_TEMPERATURE", "Nhiet do cao"),
                    ("HIGH_HUMIDITY", "Do am cao"),
                    ("HIGH_SMOKE_LEVEL", "Muc khoi cao"),
                    ("SMOKE_DETECTED", "Phat hien khoi"),
                    ("DEVICE_OFFLINE", "Thiet bi offline"),
                ],
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="alert",
            name="severity",
            field=models.CharField(
                choices=[
                    ("LOW", "Thap"),
                    ("MEDIUM", "Trung binh"),
                    ("HIGH", "Cao"),
                    ("CRITICAL", "Nghiem trong"),
                ],
                default="MEDIUM",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="devicecommand",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Dang cho xu ly"),
                    ("PUBLISHED", "Da publish MQTT"),
                    ("DONE", "ESP da thuc hien"),
                    ("FAILED", "That bai"),
                    ("TIMEOUT", "Qua thoi gian phan hoi"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="esp",
            name="status",
            field=models.CharField(
                choices=[
                    ("UNCLAIMED", "Chua gan"),
                    ("ONLINE", "Dang online"),
                    ("OFFLINE", "Dang offline"),
                    ("ERROR", "Loi"),
                ],
                default="UNCLAIMED",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="mqttmessage",
            name="direction",
            field=models.CharField(
                choices=[
                    ("INBOUND", "ESP gui len Django"),
                    ("OUTBOUND", "Django gui xuong ESP"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="mqttmessage",
            name="message_type",
            field=models.CharField(
                choices=[
                    ("PING", "Ping online"),
                    ("ACK", "Xac nhan MQTT"),
                    ("SENSOR", "Du lieu cam bien"),
                    ("STATE", "Trang thai switch"),
                    ("SET", "Lenh dieu khien"),
                    ("UNKNOWN", "Khong xac dinh"),
                ],
                default="UNKNOWN",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="sensorreading",
            name="humidity",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sensorreading",
            name="recorded_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name="sensorreading",
            name="smoke_level",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sensorreading",
            name="temperature",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="switch",
            name="actual_state",
            field=models.CharField(
                choices=[("ON", "Bat"), ("OFF", "Tat")],
                default="OFF",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="switch",
            name="desired_state",
            field=models.CharField(
                choices=[("ON", "Bat"), ("OFF", "Tat")],
                default="OFF",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="switch",
            name="sync_status",
            field=models.CharField(
                choices=[
                    ("SYNCED", "Da dong bo"),
                    ("PENDING", "Dang cho ESP xac nhan"),
                    ("FAILED", "Dong bo that bai"),
                ],
                default="SYNCED",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="esp",
            index=models.Index(fields=["hashcode"], name="esps_hashcod_7f8f2a_idx"),
        ),
        migrations.AddIndex(
            model_name="esp",
            index=models.Index(fields=["status"], name="esps_status_228b13_idx"),
        ),
        migrations.AddIndex(
            model_name="esp",
            index=models.Index(fields=["home", "status"], name="esps_home_id_372272_idx"),
        ),
    ]
