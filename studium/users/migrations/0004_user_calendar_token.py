from django.db import migrations, models
from django.utils.crypto import get_random_string


def populate_calendar_tokens(apps, schema_editor):
    User = apps.get_model("users", "User")
    for user in User.objects.all():
        if not user.calendar_token:
            user.calendar_token = get_random_string(64)
            user.save(update_fields=["calendar_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_user_learning_seconds"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="calendar_token",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.RunPython(populate_calendar_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="calendar_token",
            field=models.CharField(blank=True, max_length=64, unique=True),
        ),
    ]
