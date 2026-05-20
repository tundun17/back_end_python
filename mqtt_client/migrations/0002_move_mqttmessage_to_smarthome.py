from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("mqtt_client", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name="MQTTMessage",
                ),
            ],
            database_operations=[],
        ),
    ]
