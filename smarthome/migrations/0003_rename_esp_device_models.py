import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("smarthome", "0002_alter_espdevice_device_code"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="ESPDevice",
            new_name="ESP",
        ),
        migrations.RenameModel(
            old_name="Light",
            new_name="Device",
        ),
        migrations.RenameField(
            model_name="device",
            old_name="device",
            new_name="esp",
        ),
        migrations.RenameField(
            model_name="devicecommand",
            old_name="light",
            new_name="controlled_device",
        ),
        migrations.AlterModelTable(
            name="esp",
            table="esps",
        ),
        migrations.AlterModelTable(
            name="device",
            table="devices",
        ),
        migrations.AlterField(
            model_name="device",
            name="esp",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="devices",
                to="smarthome.esp",
            ),
        ),
        migrations.AlterField(
            model_name="device",
            name="room",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="devices",
                to="smarthome.room",
            ),
        ),
        migrations.AlterField(
            model_name="devicecommand",
            name="command_type",
            field=models.CharField(default="SET_DEVICE_STATE", max_length=50),
        ),
        migrations.AlterField(
            model_name="devicecommand",
            name="controlled_device",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="commands",
                to="smarthome.device",
            ),
        ),
        migrations.AlterModelOptions(
            name="device",
            options={"ordering": ["esp", "device_code"]},
        ),
        migrations.AlterUniqueTogether(
            name="device",
            unique_together={("esp", "device_code")},
        ),
    ]
