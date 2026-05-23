from django import forms
from django.forms import inlineformset_factory

from .models import (
    AudioBlock,
    Category,
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
DATETIME_INPUT_FORMATS = ["%Y-%m-%dT%H:%M",
                          "%Y-%m-%d %H:%M:%S",
                          "%Y-%m-%d %H:%M"]


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
        fields = ("name", "description", "image", "category", "is_published")
        labels = {
            "name": "Название",
            "description": "Описание",
            "image": "Обложка",
            "category": "Категория",
            "is_published": "Опубликован (виден в каталоге)",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "Название курса"}
            ),
            "description": forms.Textarea(
                attrs={"class":INPUT_CLASS, "rows":5, "placeholder":"Описание курса"}
            ),
            "image": forms.FileInput(attrs={"class": INPUT_CLASS}),
            "category": forms.Select(attrs={"class": INPUT_CLASS}),
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


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ("name",)
        labels = {"name": "Название урока"}
        widgets = {
            "name": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "Название урока"}
            ),
        }


class TextBlockForm(forms.ModelForm):
    class Meta:
        model = TextBlock
        fields = ("text",)
        labels = {"text": "Текст"}
        widgets = {
            "text": forms.Textarea(
                attrs={"class":INPUT_CLASS, "rows":8, "placeholder":"Текст урока"}
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
        widgets = {"teachers_file": forms.FileInput(attrs={"class":INPUT_CLASS})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_file_edit_mode(self, ("teachers_file",))


class TextQuestionForm(forms.ModelForm):
    class Meta:
        model = TextQuestion
        fields = ("question", "correct_answer", "deadline", "max_attempts")
        labels = {
            "question": "Вопрос",
            "correct_answer": "Правильный ответ",
            "deadline": "Срок сдачи (необязательно)",
            "max_attempts": "Максимум попыток",
        }
        widgets = {
            "question": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "correct_answer": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "deadline": _datetime_widget(),
            "max_attempts": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deadline"].required = False
        self.fields["deadline"].input_formats = DATETIME_INPUT_FORMATS


class ChoiceQuestionForm(forms.ModelForm):
    class Meta:
        model = ChoiceQuestion
        fields = ("question", "max_choices", "deadline", "max_attempts")
        labels = {
            "question": "Вопрос",
            "max_choices": "Сколько вариантов можно отметить верными",
            "deadline": "Срок сдачи (необязательно)",
            "max_attempts": "Максимум попыток",
        }
        widgets = {
            "question": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "max_choices": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1}),
            "deadline": _datetime_widget(),
            "max_attempts": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deadline"].required = False
        self.fields["deadline"].input_formats = DATETIME_INPUT_FORMATS


class FileQuestionForm(forms.ModelForm):
    class Meta:
        model = FileQuestion
        fields = ("title", "description", "deadline", "max_attempts")
        labels = {
            "title": "Название задания",
            "description": "Описание",
            "deadline": "Срок сдачи (необязательно)",
            "max_attempts": "Максимум попыток",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "description": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 4}),
            "deadline": _datetime_widget(),
            "max_attempts": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deadline"].required = False
        self.fields["deadline"].input_formats = DATETIME_INPUT_FORMATS


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
