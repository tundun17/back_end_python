import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mqtt_client", "0002_move_mqttmessage_to_smarthome"),
        ("smarthome", "0003_rename_esp_device_models"),
    ]

    operations = [
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
        migrations.RenameModel(
            old_name="Device",
            new_name="Switch",
        ),
        migrations.RenameField(
            model_name="switch",
            old_name="esp",
            new_name="esp_device",
        ),
        migrations.RenameField(
            model_name="switch",
            old_name="device_code",
            new_name="switch_code",
        ),
        migrations.AlterModelTable(
            name="switch",
            table="switches",
        ),
        migrations.AlterField(
            model_name="switch",
            name="esp_device",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="switches",
                to="smarthome.esp",
            ),
        ),
        migrations.AlterField(
            model_name="switch",
            name="room",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="switches",
                to="smarthome.room",
            ),
        ),
        migrations.RemoveField(
            model_name="switch",
            name="gpio_pin",
        ),
        migrations.AlterModelOptions(
            name="switch",
            options={"ordering": ["esp_device", "switch_code"]},
        ),
        migrations.AlterUniqueTogether(
            name="switch",
            unique_together={("esp_device", "switch_code")},
        ),
        migrations.RenameField(
            model_name="devicecommand",
            old_name="device",
            new_name="esp",
        ),
        migrations.RenameField(
            model_name="devicecommand",
            old_name="controlled_device",
            new_name="switch",
        ),
        migrations.RenameField(
            model_name="devicecommand",
            old_name="sent_at",
            new_name="published_at",
        ),
        migrations.AlterField(
            model_name="devicecommand",
            name="esp",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="commands",
                to="smarthome.esp",
            ),
        ),
        migrations.AlterField(
            model_name="devicecommand",
            name="switch",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="commands",
                to="smarthome.switch",
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
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="MQTTMessage",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("topic", models.CharField(max_length=255)),
                        (
                            "direction",
                            models.CharField(
                                choices=[
                                    ("INBOUND", "ESP gui len Django"),
                                    ("OUTBOUND", "Django gui xuong ESP"),
                                ],
                                max_length=20,
                            ),
                        ),
                        (
                            "message_type",
                            models.CharField(
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
                        ("payload", models.JSONField(blank=True, default=dict)),
                        ("is_processed", models.BooleanField(default=False)),
                        ("error_message", models.TextField(blank=True, null=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "device",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="mqtt_messages",
                                to="smarthome.esp",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "mqtt_messages",
                        "ordering": ["-created_at"],
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE mqtt_messages "
                        "ADD COLUMN device_id bigint NULL REFERENCES esps(id) "
                        "DEFERRABLE INITIALLY DEFERRED"
                    ),
                    reverse_sql=(
                        "ALTER TABLE mqtt_messages DROP COLUMN device_id"
                    ),
                ),
            ],
        ),
    ]
