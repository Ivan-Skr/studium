from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0004_certificatetemplate_coursecompletion_lessonprogress_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="lessonprogress",
            name="score_percent",
            field=models.PositiveSmallIntegerField(
                default=0,
                validators=[MinValueValidator(0), MaxValueValidator(100)],
                verbose_name="Процент сдачи",
            ),
        ),
    ]
