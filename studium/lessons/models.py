from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from polymorphic.models import PolymorphicModel

from .validators import FileSizeValidator, UploadExtensionValidator


class Category(models.Model):
    name = models.CharField("Название", max_length=50)
    slug = models.SlugField("Слаг", unique=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class Course(models.Model):
    name = models.CharField("Название", max_length=30)
    description = models.TextField("Описание")
    image = models.ImageField("Обложка", upload_to="images/courses/covers/", blank=True)
    detail_image = models.ImageField(
        "Фото для страницы курса",
        upload_to="images/courses/details/",
        null=True,
        blank=True,
    )
    enrollment_code = models.CharField(
        "Кодовое слово для записи",
        max_length=50,
        blank=True,
        help_text="Оставьте пустым, чтобы студенты записывались сразу.",
    )
    is_published = models.BooleanField("Опубликован", default=True)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Автор",
        on_delete=models.CASCADE,
        related_name="courses_authored",
    )
    category = models.ForeignKey(
        Category,
        verbose_name="Категория",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses",
    )

    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"
        indexes = [
            models.Index(fields=["is_published", "created_at"]),
        ]

    def __str__(self):
        return self.name

    @property
    def requires_enrollment_code(self):
        return bool(self.enrollment_code.strip())

    @property
    def display_detail_image(self):
        return self.detail_image or self.image


class CourseEnrollment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На рассмотрении"
        APPROVED = "approved", "Записан"
        REJECTED = "rejected", "Отклонена"

    course = models.ForeignKey(
        Course,
        verbose_name="Курс",
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Студент",
        on_delete=models.CASCADE,
        related_name="course_enrollments",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    group = models.ForeignKey(
        "StudentGroup",
        verbose_name="Группа",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enrollments",
    )
    requested_at = models.DateTimeField("Заявка отправлена", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Запись на курс"
        verbose_name_plural = "Записи на курсы"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "student"],
                name="unique_course_enrollment",
            ),
        ]
        indexes = [
            models.Index(fields=["course", "status"]),
            models.Index(fields=["student", "status"]),
        ]
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.student} -> {self.course} ({self.get_status_display()})"


class LessonProgress(models.Model):
    lesson = models.ForeignKey(
        "Lesson",
        verbose_name="Урок",
        on_delete=models.CASCADE,
        related_name="progress",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Студент",
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )
    completed_at = models.DateTimeField("Завершен", default=timezone.now)
    score_percent = models.PositiveSmallIntegerField(
        "Процент сдачи",
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        verbose_name = "Прогресс урока"
        verbose_name_plural = "Прогресс уроков"
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "student"],
                name="unique_lesson_progress",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "lesson"]),
        ]

    def __str__(self):
        return f"{self.student} -> {self.lesson}"


class LessonStudyTime(models.Model):
    lesson = models.ForeignKey(
        "Lesson",
        verbose_name="Урок",
        on_delete=models.CASCADE,
        related_name="study_times",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Студент",
        on_delete=models.CASCADE,
        related_name="lesson_study_times",
    )
    seconds = models.PositiveIntegerField("Секунды", default=0)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Время на урок"
        verbose_name_plural = "Время на уроках"
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "student"],
                name="unique_lesson_study_time",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "lesson"]),
        ]

    def __str__(self):
        return f"{self.student} → {self.lesson}: {self.seconds} сек."


class CourseCompletion(models.Model):
    course = models.ForeignKey(
        Course,
        verbose_name="Курс",
        on_delete=models.CASCADE,
        related_name="completions",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Студент",
        on_delete=models.CASCADE,
        related_name="course_completions",
    )
    completed_at = models.DateTimeField("Завершен", default=timezone.now)

    class Meta:
        verbose_name = "Завершение курса"
        verbose_name_plural = "Завершения курсов"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "student"],
                name="unique_course_completion",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "course"]),
        ]

    def __str__(self):
        return f"{self.student} -> {self.course}"


class CertificateTemplate(models.Model):
    course = models.ForeignKey(
        Course,
        verbose_name="Курс",
        on_delete=models.CASCADE,
        related_name="certificate_templates",
    )
    title = models.CharField("Название", max_length=100)
    description = models.TextField("Описание", blank=True)
    image = models.ImageField(
        "Изображение",
        upload_to="images/certificates/",
        null=True,
        blank=True,
    )
    is_completion_certificate = models.BooleanField(
        "Выдается за прохождение курса",
        default=False,
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлен", auto_now=True)

    class Meta:
        verbose_name = "Сертификат курса"
        verbose_name_plural = "Сертификаты курсов"
        constraints = [
            models.UniqueConstraint(
                fields=["course"],
                condition=models.Q(is_completion_certificate=True),
                name="unique_completion_certificate_per_course",
            ),
        ]
        ordering = ["-is_completion_certificate", "title"]

    def __str__(self):
        return self.title


class StudentCertificate(models.Model):
    template = models.ForeignKey(
        CertificateTemplate,
        verbose_name="Шаблон сертификата",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_certificates",
    )
    course = models.ForeignKey(
        Course,
        verbose_name="Курс",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_certificates",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Студент",
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    title = models.CharField("Название", max_length=100)
    description = models.TextField("Описание", blank=True)
    image = models.ImageField(
        "Изображение",
        upload_to="images/student_certificates/",
        null=True,
        blank=True,
    )
    is_completion_certificate = models.BooleanField(default=False)
    issued_at = models.DateTimeField("Выдан", default=timezone.now)

    class Meta:
        verbose_name = "Сертификат студента"
        verbose_name_plural = "Сертификаты студентов"
        constraints = [
            models.UniqueConstraint(
                fields=["template", "student"],
                name="unique_student_certificate_template",
            ),
        ]
        ordering = ["-issued_at"]

    def __str__(self):
        return f"{self.student} -> {self.title}"


class Lesson(models.Model):
    name = models.CharField("Название", max_length=50)
    deadline = models.DateTimeField(
        "Дедлайн урока",
        null=True,
        blank=True,
        help_text="Общий срок сдачи всех заданий урока.",
    )
    course = models.ForeignKey(
        Course,
        verbose_name="Курс",
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    order = models.PositiveSmallIntegerField(
        "Порядок", validators=[MinValueValidator(1)]
    )

    class Meta:
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"
        ordering = ["order"]
        indexes = [
            models.Index(fields=["course", "order"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.pk and self.course_id and (self.order is None or self.order <= 0):
            max_order = (
                Lesson.objects.filter(course_id=self.course_id)
                .aggregate(max_order=models.Max("order"))
                .get("max_order")
                or 0
            )
            self.order = max_order + 1
        super().save(*args, **kwargs)


class Block(PolymorphicModel):
    lesson = models.ForeignKey(
        Lesson,
        verbose_name="Урок",
        on_delete=models.CASCADE,
        related_name="blocks",
    )
    order = models.PositiveSmallIntegerField(
        "Порядок", validators=[MinValueValidator(1)]
    )

    class Meta:
        verbose_name = "Блок"
        verbose_name_plural = "Блоки"
        ordering = ["order"]
        indexes = [
            models.Index(fields=["lesson", "order"]),
        ]

    def save(self, *args, **kwargs):
        if not self.pk and self.lesson_id and (self.order is None or self.order <= 0):
            max_order = (
                Block.objects.filter(lesson_id=self.lesson_id)
                .aggregate(max_order=models.Max("order"))
                .get("max_order")
                or 0
            )
            self.order = max_order + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self._meta.verbose_name} (#{self.order})"


class TextBlock(Block):
    text = models.TextField("Текст")

    class Meta:
        verbose_name = "Текстовый блок"
        verbose_name_plural = "Текстовые блоки"

    def __str__(self):
        return f"{self._meta.verbose_name} (#{self.order})"


class ImageBlock(Block):
    image = models.ImageField(
        "Изображение",
        upload_to="images/imageblocks/",
        validators=[
            FileSizeValidator(10),
            UploadExtensionValidator({"jpg", "jpeg", "png", "webp"}),
        ],
    )

    class Meta:
        verbose_name = "Фото блок"
        verbose_name_plural = "Фото блоки"

    def __str__(self):
        return f"{self._meta.verbose_name} (#{self.order})"


class VideoBlock(Block):
    video = models.FileField(
        "Видео",
        upload_to="videoblocks/",
        validators=[
            FileSizeValidator(200),
            UploadExtensionValidator({"mp4", "webm", "mov", "m4v"}),
        ],
    )

    class Meta:
        verbose_name = "Видео блок"
        verbose_name_plural = "Видео блоки"

    def __str__(self):
        return f"{self._meta.verbose_name} (#{self.order})"


class AudioBlock(Block):
    audio = models.FileField(
        "Аудио",
        upload_to="audioblocks/",
        validators=[
            FileSizeValidator(50),
            UploadExtensionValidator({"mp3", "wav", "ogg", "m4a", "aac"}),
        ],
    )

    class Meta:
        verbose_name = "Аудио блок"
        verbose_name_plural = "Аудио блоки"

    def __str__(self):
        return f"{self._meta.verbose_name} (#{self.order})"


class TeacherFileBlock(Block):
    teachers_file = models.FileField(
        "Файл",
        upload_to="teachers_files/",
        validators=[
            FileSizeValidator(50),
            UploadExtensionValidator(
                {
                    "pdf",
                    "doc",
                    "docx",
                    "ppt",
                    "pptx",
                    "xls",
                    "xlsx",
                    "zip",
                    "rar",
                    "7z",
                    "txt",
                }
            ),
        ],
    )

    class Meta:
        verbose_name = "Блок файла учителя"
        verbose_name_plural = "Блоки файла учителя"

    def __str__(self):
        return f"{self._meta.verbose_name} (#{self.order})"


class TextQuestion(Block):
    question = models.CharField("Вопрос", max_length=200)
    correct_answer = models.CharField("Правильный ответ", max_length=100)
    max_attempts = models.PositiveSmallIntegerField(
        "Максимум попыток",
        default=3,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        verbose_name = "Текстовый вопрос"
        verbose_name_plural = "Текстовые вопросы"

    def __str__(self):
        return f"{self._meta.verbose_name}: {self.question}"


class ChoiceQuestion(Block):
    question = models.CharField("Вопрос", max_length=200)
    max_choices = models.PositiveSmallIntegerField(
        "Максимум правильных вариантов",
        default=1,
        validators=[MinValueValidator(1)],
    )
    max_attempts = models.PositiveSmallIntegerField(
        "Максимум попыток",
        default=3,
        validators=[MinValueValidator(1)],
    )

    def clean(self):
        if not self.pk:
            return
        correct_count = self.answers.filter(is_correct=True).count()

        if correct_count > self.max_choices:
            raise ValidationError(
                f"Уже есть {correct_count} правильных ответов, "
                f"что больше max_choices={self.max_choices}"
            )

    class Meta:
        verbose_name = "Вопрос с выбором"
        verbose_name_plural = "Вопросы с выбором"

    def __str__(self):
        return f"{self._meta.verbose_name}: {self.question}"


class FileQuestion(Block):
    title = models.CharField("Название", max_length=50)
    description = models.TextField("Описание")
    max_attempts = models.PositiveSmallIntegerField(
        "Максимум попыток",
        default=3,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        verbose_name = "Вопрос с файлом"
        verbose_name_plural = "Вопросы с файлами"

    def __str__(self):
        return f"{self._meta.verbose_name}: {self.title}"


class ChoiceAnswer(models.Model):
    question = models.ForeignKey(
        ChoiceQuestion,
        verbose_name="Вопрос",
        on_delete=models.CASCADE,
        related_name="answers",
    )
    text = models.CharField("Ответ", max_length=100)
    is_correct = models.BooleanField("Верно", default=False)

    class Meta:
        verbose_name = "Вариант ответа"
        verbose_name_plural = "Варианты ответов"
        indexes = [
            models.Index(fields=["question"]),
        ]

    def __str__(self):
        return self.text


class TextAnswerSubmission(models.Model):
    question = models.ForeignKey(
        TextQuestion,
        verbose_name="Вопрос",
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Студент",
        on_delete=models.CASCADE,
        related_name="text_answer_submissions",
    )
    answer = models.CharField("Ответ", max_length=100)
    attempt = models.PositiveSmallIntegerField(
        "Попытка",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    submitted_at = models.DateTimeField("Отправлено", default=timezone.now)

    class Meta:
        verbose_name = "Отправленный текстовый ответ"
        verbose_name_plural = "Отправленные текстовые ответы"
        indexes = [
            models.Index(fields=["student", "question"]),
            models.Index(fields=["student", "question", "attempt"]),
        ]
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.student} → {self.question} (попытка {self.attempt})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        if self.question_id and self.question.lesson.deadline:
            if timezone.now() > self.question.lesson.deadline:
                raise ValidationError(
                    "Дедлайн урока уже прошёл. Нельзя отправить ответ."
                )

        if self.attempt is None and self.student_id and self.question_id:
            last = (
                TextAnswerSubmission.objects.filter(
                    student_id=self.student_id,
                    question_id=self.question_id,
                )
                .order_by("-attempt")
                .values_list("attempt", flat=True)
                .first()
            )
            next_attempt = 1 if last is None else (last + 1)
            if next_attempt > self.question.max_attempts:
                raise ValidationError(
                    "Превышено максимальное число попыток "
                    f"({self.question.max_attempts})."
                )
            self.attempt = next_attempt


class ChoiceAnswerSubmission(models.Model):
    question = models.ForeignKey(
        ChoiceQuestion,
        verbose_name="Вопрос",
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Студент",
        on_delete=models.CASCADE,
        related_name="choice_answer_submissions",
    )
    selected = models.ManyToManyField(
        ChoiceAnswer,
        verbose_name="Выбрано",
        related_name="choice_submissions",
        through="ChoiceAnswerSelection",
    )
    attempt = models.PositiveSmallIntegerField(
        "Попытка",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    submitted_at = models.DateTimeField("Отправлено", default=timezone.now)

    class Meta:
        verbose_name = "Отправленный выбранный ответ"
        verbose_name_plural = "Отправленные выбранные ответы"
        indexes = [
            models.Index(fields=["student", "question"]),
            models.Index(fields=["student", "question", "attempt"]),
        ]
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"Ответы: {self.student} → {self.question}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        if self.question_id and self.question.lesson.deadline:
            if timezone.now() > self.question.lesson.deadline:
                raise ValidationError(
                    "Дедлайн урока уже прошёл. Нельзя отправить ответ."
                )

        if self.attempt is None and self.student_id and self.question_id:
            last = (
                ChoiceAnswerSubmission.objects.filter(
                    student_id=self.student_id,
                    question_id=self.question_id,
                )
                .order_by("-attempt")
                .values_list("attempt", flat=True)
                .first()
            )
            next_attempt = 1 if last is None else (last + 1)
            if next_attempt > self.question.max_attempts:
                raise ValidationError(
                    "Превышено максимальное число попыток "
                    f"({self.question.max_attempts})."
                )
            self.attempt = next_attempt


class ChoiceAnswerSelection(models.Model):
    submission = models.ForeignKey(
        ChoiceAnswerSubmission,
        on_delete=models.CASCADE,
        related_name="selections",
        verbose_name="Отправка",
    )
    answer = models.ForeignKey(
        ChoiceAnswer,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="Выбранный вариант",
    )
    selected_at = models.DateTimeField("Выбрано", auto_now_add=True)

    class Meta:
        verbose_name = "Выбор варианта"
        verbose_name_plural = "Выборы вариантов"
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "answer"],
                name="unique_answer_per_submission",
            )
        ]
        indexes = [
            models.Index(fields=["submission"]),
        ]

    def __str__(self):
        return f"{self.submission} — {self.answer}"

    def clean(self):
        if self.submission_id and self.answer_id:
            if self.answer.question_id != self.submission.question_id:
                raise ValidationError(
                    "Нельзя выбрать вариант ответа от другого вопроса."
                )


class FileAnswerSubmission(models.Model):
    question = models.ForeignKey(
        FileQuestion,
        verbose_name="Вопрос",
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Студент",
        on_delete=models.CASCADE,
        related_name="file_answer_submissions",
    )
    file = models.FileField(
        "Файл",
        upload_to="students_files/",
        validators=[
            FileSizeValidator(50),
            UploadExtensionValidator(
                {
                    "pdf",
                    "doc",
                    "docx",
                    "png",
                    "jpg",
                    "jpeg",
                    "zip",
                    "rar",
                    "7z",
                }
            ),
        ],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    grade = models.PositiveSmallIntegerField(
        "Оценка",
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    teacher_comment = models.TextField("Комментарий преподавателя", blank=True)

    class Meta:
        verbose_name = "Отправленный файл студента"
        verbose_name_plural = "Отправленные файлы студента"
        indexes = [
            models.Index(fields=["student", "question"]),
        ]

    def __str__(self):
        return f"{self.student} → {self.question}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        if self.question_id and self.question.lesson.deadline:
            if timezone.now() > self.question.lesson.deadline:
                raise ValidationError(
                    "Дедлайн урока уже прошёл. Нельзя отправить файл."
                )

        if self.student_id and self.question_id:
            existing_attempts = (
                FileAnswerSubmission.objects.filter(
                    student_id=self.student_id,
                    question_id=self.question_id,
                )
                .exclude(pk=self.pk)
                .count()
            )
            if existing_attempts >= self.question.max_attempts:
                raise ValidationError(
                    "Превышено максимальное число попыток "
                    f"({self.question.max_attempts})."
                )


class StudentGroup(models.Model):
    course = models.ForeignKey(
        Course,
        verbose_name="Курс",
        on_delete=models.CASCADE,
        related_name="student_groups",
    )
    name = models.CharField("Название группы", max_length=100)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Группа студентов"
        verbose_name_plural = "Группы студентов"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "name"],
                name="unique_student_group_name_per_course",
            ),
        ]

    def __str__(self):
        return f"{self.name} — {self.course}"
