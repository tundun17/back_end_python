from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("smarthome", "0008_remove_activitylog_activity_lo_user_id_d23b30_idx_and_more"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="AutomationRule",
            new_name="Automation",
        ),
        migrations.AlterModelTable(
            name="automation",
            table="automation",
        ),
        migrations.RenameIndex(
            model_name="automation",
            old_name="automation__sensor__c89bc0_idx",
            new_name="automation_sensor__234549_idx",
        ),
        migrations.RenameIndex(
            model_name="automation",
            old_name="automation__target__73c975_idx",
            new_name="automation_target__fb45bc_idx",
        ),
        migrations.RenameIndex(
            model_name="automation",
            old_name="automation__alert_t_5075d0_idx",
            new_name="automation_alert_t_12db95_idx",
        ),
    ]
