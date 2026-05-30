import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0005_lessonprogress_score_percent"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentGroup",
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
                (
                    "name",
                    models.CharField(max_length=100, verbose_name="Название группы"),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Создана"),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_groups",
                        to="lessons.course",
                        verbose_name="Курс",
                    ),
                ),
            ],
            options={
                "verbose_name": "Группа студентов",
                "verbose_name_plural": "Группы студентов",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="courseenrollment",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="enrollments",
                to="lessons.studentgroup",
                verbose_name="Группа",
            ),
        ),
        migrations.CreateModel(
            name="LessonStudyTime",
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
                (
                    "seconds",
                    models.PositiveIntegerField(default=0, verbose_name="Секунды"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Обновлено"),
                ),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="study_times",
                        to="lessons.lesson",
                        verbose_name="Урок",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lesson_study_times",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Студент",
                    ),
                ),
            ],
            options={
                "verbose_name": "Время на урок",
                "verbose_name_plural": "Время на уроках",
            },
        ),
        migrations.AddConstraint(
            model_name="studentgroup",
            constraint=models.UniqueConstraint(
                fields=("course", "name"),
                name="unique_student_group_name_per_course",
            ),
        ),
        migrations.AddIndex(
            model_name="lessonstudytime",
            index=models.Index(
                fields=["student", "lesson"],
                name="lessons_les_student_lesson_time_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="lessonstudytime",
            constraint=models.UniqueConstraint(
                fields=("lesson", "student"),
                name="unique_lesson_study_time",
            ),
        ),
    ]
