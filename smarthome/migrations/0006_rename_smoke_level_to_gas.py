from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("smarthome", "0005_remove_switch_switches_room_id_11c66a_idx_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="sensorreading",
            old_name="smoke_level",
            new_name="gas",
        ),
    ]
