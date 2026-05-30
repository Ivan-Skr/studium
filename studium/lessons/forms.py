from django import forms
from django.forms import inlineformset_factory

from .models import (
    AudioBlock,
    Category,
    CertificateTemplate,
    ChoiceAnswer,
    ChoiceQuestion,
    Course,
    FileQuestion,
    ImageBlock,
    Lesson,
    TeacherFileBlock,
    TextBlock,
    TextQuestion,
    VideoBlock,
)

INPUT_CLASS = (
    "w-full px-4 py-2.5 rounded-lg border border-gray-300 "
    "bg-white text-gray-900 "  # Стили для светлой темы
    "dark:border-slate-600 dark:bg-slate-800 dark:text-gray-100 "
    "focus:outline-none focus:ring-2 focus:ring-blue-500"
)
CHECKBOX_CLASS = "rounded border-gray-300 text-blue-600"
DATETIME_INPUT_FORMATS = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]


def _datetime_widget():
    return forms.DateTimeInput(
        format="%Y-%m-%dT%H:%M",
        attrs={"type": "datetime-local", "class": INPUT_CLASS},
    )


def _apply_file_edit_mode(form, file_fields):
    if form.instance and form.instance.pk:
        for name in file_fields:
            if name in form.fields:
                form.fields[name].required = False


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = (
            "name",
            "description",
            "image",
            "detail_image",
            "category",
            "enrollment_code",
            "is_published",
        )
        labels = {
            "name": "Название",
            "description": "Описание",
            "image": "Обложка",
            "detail_image": "Фото для страницы курса",
            "category": "Категория",
            "enrollment_code": "Кодовое слово",
            "is_published": "Опубликован (виден в каталоге)",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "Название курса"}
            ),
            "description": forms.Textarea(
                attrs={"class": INPUT_CLASS, "rows": 5, "placeholder": "Описание курса"}
            ),
            "image": forms.FileInput(attrs={"class": INPUT_CLASS}),
            "detail_image": forms.FileInput(attrs={"class": INPUT_CLASS}),
            "category": forms.Select(attrs={"class": INPUT_CLASS}),
            "enrollment_code": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "Оставьте пустым для открытой записи",
                }
            ),
            "is_published": forms.CheckboxInput(
                attrs={"class": "rounded border-gray-300 text-blue-600"}
            ),
        }

    def __init__(self, *args, is_edit=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.order_by("name")
        self.fields["category"].required = False
        self.fields["category"].empty_label = "Без категории"
        if is_edit:
            self.fields["image"].required = False
            self.fields["detail_image"].required = False


class EnrollmentCodeForm(forms.Form):
    code = forms.CharField(
        label="Кодовое слово",
        max_length=50,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if self.course and code != self.course.enrollment_code:
            raise forms.ValidationError("Неверное кодовое слово.")
        return code


class CertificateTemplateForm(forms.ModelForm):
    class Meta:
        model = CertificateTemplate
        fields = ("title", "description", "image", "is_completion_certificate")
        labels = {
            "title": "Название сертификата",
            "description": "Описание",
            "image": "Изображение",
            "is_completion_certificate": "Выдавать за прохождение всего курса",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "description": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
            "image": forms.FileInput(attrs={"class": INPUT_CLASS}),
            "is_completion_certificate": forms.CheckboxInput(
                attrs={"class": CHECKBOX_CLASS}
            ),
        }

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course
        if self.instance and self.instance.pk:
            self.fields["image"].required = False

        existing_completion = None
        if course is not None:
            existing_completion = course.certificate_templates.filter(
                is_completion_certificate=True
            ).first()

        if existing_completion and (
            not self.instance.pk or self.instance.pk != existing_completion.pk
        ):
            self.fields["is_completion_certificate"].disabled = True
            self.fields["is_completion_certificate"].help_text = (
                "Сертификат за прохождение курса уже создан."
            )

    def clean_is_completion_certificate(self):
        value = self.cleaned_data.get("is_completion_certificate")
        if not value or self.course is None:
            return value
        existing = self.course.certificate_templates.filter(
            is_completion_certificate=True
        )
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("Для курса уже есть сертификат за прохождение.")
        return value


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ("name", "deadline")
        labels = {
            "name": "Название урока",
            "deadline": "Дедлайн урока",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "Название урока"}
            ),
            "deadline": _datetime_widget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deadline"].required = False
        self.fields["deadline"].input_formats = DATETIME_INPUT_FORMATS


class TextBlockForm(forms.ModelForm):
    class Meta:
        model = TextBlock
        fields = ("text",)
        labels = {"text": "Текст"}
        widgets = {
            "text": forms.Textarea(
                attrs={"class": INPUT_CLASS, "rows": 8, "placeholder": "Текст урока"}
            ),
        }


class ImageBlockForm(forms.ModelForm):
    class Meta:
        model = ImageBlock
        fields = ("image",)
        labels = {"image": "Изображение"}
        widgets = {"image": forms.FileInput(attrs={"class": INPUT_CLASS})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_file_edit_mode(self, ("image",))


class VideoBlockForm(forms.ModelForm):
    class Meta:
        model = VideoBlock
        fields = ("video",)
        labels = {"video": "Видеофайл"}
        widgets = {"video": forms.FileInput(attrs={"class": INPUT_CLASS})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_file_edit_mode(self, ("video",))


class AudioBlockForm(forms.ModelForm):
    class Meta:
        model = AudioBlock
        fields = ("audio",)
        labels = {"audio": "Аудиофайл"}
        widgets = {"audio": forms.FileInput(attrs={"class": INPUT_CLASS})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_file_edit_mode(self, ("audio",))


class TeacherFileBlockForm(forms.ModelForm):
    class Meta:
        model = TeacherFileBlock
        fields = ("teachers_file",)
        labels = {"teachers_file": "Файл для студентов"}
        widgets = {"teachers_file": forms.FileInput(attrs={"class": INPUT_CLASS})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_file_edit_mode(self, ("teachers_file",))


class TextQuestionForm(forms.ModelForm):
    class Meta:
        model = TextQuestion
        fields = ("question", "correct_answer", "max_attempts")
        labels = {
            "question": "Вопрос",
            "correct_answer": "Правильный ответ",
            "max_attempts": "Максимум попыток",
        }
        widgets = {
            "question": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "correct_answer": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "max_attempts": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ChoiceQuestionForm(forms.ModelForm):
    class Meta:
        model = ChoiceQuestion
        fields = ("question", "max_choices", "max_attempts")
        labels = {
            "question": "Вопрос",
            "max_choices": "Сколько вариантов можно отметить верными",
            "max_attempts": "Максимум попыток",
        }
        widgets = {
            "question": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "max_choices": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1}),
            "max_attempts": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class FileQuestionForm(forms.ModelForm):
    class Meta:
        model = FileQuestion
        fields = ("title", "description", "max_attempts")
        labels = {
            "title": "Название задания",
            "description": "Описание",
            "max_attempts": "Максимум попыток",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "description": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 4}),
            "max_attempts": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ChoiceAnswerForm(forms.ModelForm):
    class Meta:
        model = ChoiceAnswer
        fields = ("text", "is_correct")
        labels = {"text": "Вариант", "is_correct": "Верный"}
        widgets = {
            "text": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "is_correct": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }


class BaseChoiceAnswerFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        answers = []
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            text = form.cleaned_data.get("text", "").strip()
            if text:
                answers.append(form.cleaned_data)

        if len(answers) < 2:
            raise forms.ValidationError("Добавьте минимум два варианта ответа.")

        correct_count = sum(1 for a in answers if a.get("is_correct"))
        if correct_count == 0:
            raise forms.ValidationError("Отметьте хотя бы один верный вариант.")


def _choice_answer_formset_factory(*, extra: int):
    return inlineformset_factory(
        ChoiceQuestion,
        ChoiceAnswer,
        form=ChoiceAnswerForm,
        formset=BaseChoiceAnswerFormSet,
        extra=extra,
        can_delete=True,
        min_num=0,
        validate_min=False,
    )


def build_choice_answer_formset(*, instance=None, data=None):
    if data is not None:
        FormSet = _choice_answer_formset_factory(extra=0)
        return FormSet(data, instance=instance, prefix="answers")

    extra = 1 if instance and instance.pk else 2
    FormSet = _choice_answer_formset_factory(extra=extra)
    return FormSet(instance=instance, prefix="answers")
