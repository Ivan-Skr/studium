from django.db import migrations, models

def move_block_deadlines_to_lessons(apps, schema_editor):
    Lesson = apps.get_model("lessons", "Lesson")
    TextQuestion = apps.get_model("lessons", "TextQuestion")
    ChoiceQuestion = apps.get_model("lessons", "ChoiceQuestion")
    FileQuestion = apps.get_model("lessons", "FileQuestion")

    deadline_by_lesson_id = {}

    for model in (TextQuestion, ChoiceQuestion, FileQuestion):
        for block in model.objects.exclude(deadline__isnull=True).only(
            "lesson_id",
            "deadline",
        ):
            current = deadline_by_lesson_id.get(block.lesson_id)
            if current is None or block.deadline < current:
                deadline_by_lesson_id[block.lesson_id] = block.deadline

    for lesson_id, deadline in deadline_by_lesson_id.items():
        Lesson.objects.filter(pk=lesson_id, deadline__isnull=True).update(
            deadline=deadline
        )

class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0007_rename_lessons_les_student_lesson_time_idx_lessons_les_student_833c5d_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="deadline",
            field=models.DateTimeField(
                blank=True,
                help_text="Общий срок сдачи всех заданий урока.",
                null=True,
                verbose_name="Дедлайн урока",
            ),
        ),
        migrations.RunPython(
            move_block_deadlines_to_lessons,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="textquestion",
            name="deadline",
        ),
        migrations.RemoveField(
            model_name="choicequestion",
            name="deadline",
        ),
        migrations.RemoveField(
            model_name="filequestion",
            name="deadline",
        ),
    ]