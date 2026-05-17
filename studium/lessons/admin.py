from adminsortable2.admin import (
    CustomInlineFormSet,
    SortableAdminBase,
    SortableInlineAdminMixin,
)
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.forms.models import BaseInlineFormSet
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from polymorphic.admin import (
    PolymorphicChildModelAdmin,
    PolymorphicChildModelFilter,
    PolymorphicInlineSupportMixin,
    PolymorphicParentModelAdmin,
)

from lessons.models import (
    AudioBlock,
    Block,
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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class LessonInline(SortableInlineAdminMixin, admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("name",)
    ordering = ("order",)
    show_change_link = True


@admin.register(Course)
class CourseAdmin(SortableAdminBase, PolymorphicInlineSupportMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "author",
        "category",
        "is_published",
        "lesson_count",
        "created_at",
    )
    list_filter = ("is_published", "category")
    list_select_related = ("author", "category")
    search_fields = ("name", "author__username", "author__email")
    inlines = (LessonInline,)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(_lesson_count=Count("lessons"))

    @admin.display(description="Уроков", ordering="_lesson_count")
    def lesson_count(self, obj):
        return obj._lesson_count


class BlockInline(SortableInlineAdminMixin, admin.TabularInline):
    model = Block
    extra = 0
    fields = ("polymorphic_ctype",)
    readonly_fields = ("polymorphic_ctype",)
    ordering = ("order",)
    show_change_link = True


class UniqueOrderInlineFormSet(CustomInlineFormSet):
    """Проверяет уникальность order внутри текущего родителя в админке."""

    def clean(self):
        super().clean()
        seen_orders = {}

        for index, form in enumerate(self.forms, start=1):
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            order = form.cleaned_data.get("order")
            if order in (None, ""):
                continue

            if order in seen_orders:
                first_row = seen_orders[order]
                raise ValidationError(
                    "Найден дубликат порядка: "
                    f"{order}. Одинаковый order у строк #{first_row} и #{index}. "
                    "Поставьте разные значения order или перетащите строки мышкой."
                )
            seen_orders[order] = index


class LessonInlineFormSet(UniqueOrderInlineFormSet): ...


class BlockInlineFormSet(UniqueOrderInlineFormSet): ...


LessonInline.formset = LessonInlineFormSet
BlockInline.formset = BlockInlineFormSet


@admin.register(Lesson)
class LessonAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ("name", "course", "order", "blocks_count")
    list_filter = ("course",)
    list_select_related = ("course",)
    search_fields = ("name", "course__name")
    ordering = ("course", "order")
    inlines = (BlockInline,)
    readonly_fields = ("order", "add_block_links")
    fieldsets = (
        (None, {"fields": ("course", "name", "order")}),
        ("Быстрое добавление блоков", {"fields": ("add_block_links",)}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(_blocks_count=Count("blocks"))

    @admin.display(description="Блоков", ordering="_blocks_count")
    def blocks_count(self, obj):
        return obj._blocks_count

    @admin.display(description="Добавить новый блок")
    def add_block_links(self, obj):
        if not obj.pk:
            return "Сначала сохраните урок, затем можно добавить блоки."

        add_urls = (
            ("Текстовый блок", "admin:lessons_textblock_add"),
            ("Фото блок", "admin:lessons_imageblock_add"),
            ("Видео блок", "admin:lessons_videoblock_add"),
            ("Аудио блок", "admin:lessons_audioblock_add"),
            ("Блок файла учителя", "admin:lessons_teacherfileblock_add"),
            ("Текстовый вопрос", "admin:lessons_textquestion_add"),
            ("Вопрос с выбором", "admin:lessons_choicequestion_add"),
            ("Вопрос с файлом", "admin:lessons_filequestion_add"),
        )
        links = format_html_join(
            "",
            (
                '<a href="{}?lesson={}" style="display:inline-flex;align-items:center;'
                "justify-content:center;padding:8px 12px;border-radius:8px;"
                "border:1px solid #d9d9d9;background:#f8f8f8;text-decoration:none;"
                'color:#202124;font-weight:600;white-space:nowrap;">{}</a>'
            ),
            ((reverse(url_name), obj.pk, title) for title, url_name in add_urls),
        )
        return format_html(
            (
                '<div style="display:grid;'
                "grid-template-columns:repeat(auto-fit,minmax(210px,1fr));"
                'gap:8px;max-width:980px;margin-top:6px;">{}</div>'
                '<p style="margin:10px 0 0;color:#666;">'
                "Нажмите на нужный тип: откроется форма создания уже для этого урока."
                "</p>"
                '<p style="margin:6px 0 0;color:#666;">'
                "Порядок блоков ниже можно менять перетаскиванием."
                "</p>"
            ),
            links,
        )


class BaseBlockChildAdmin(PolymorphicChildModelAdmin):
    base_model = Block
    change_list_template = "admin/change_list.html"
    list_display = ("__str__", "lesson", "course_name", "order")
    list_filter = (PolymorphicChildModelFilter, "lesson__course")
    search_fields = ("lesson__name", "lesson__course__name")
    autocomplete_fields = ("lesson",)
    readonly_fields = ("order",)
    ordering = ("lesson__course", "lesson", "order")

    @admin.display(description="Курс", ordering="lesson__course__name")
    def course_name(self, obj):
        return obj.lesson.course.name

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        lesson_id = request.GET.get("lesson")
        if lesson_id:
            initial["lesson"] = lesson_id
        return initial

    def get_child_type_choices(self, request, action):
        return ()


@admin.register(TextBlock)
class TextBlockAdmin(BaseBlockChildAdmin):
    base_model = TextBlock
    show_in_index = False


@admin.register(ImageBlock)
class ImageBlockAdmin(BaseBlockChildAdmin):
    base_model = ImageBlock
    show_in_index = False


@admin.register(VideoBlock)
class VideoBlockAdmin(BaseBlockChildAdmin):
    base_model = VideoBlock
    show_in_index = False


@admin.register(AudioBlock)
class AudioBlockAdmin(BaseBlockChildAdmin):
    base_model = AudioBlock
    show_in_index = False


@admin.register(TeacherFileBlock)
class TeacherFileBlockAdmin(BaseBlockChildAdmin):
    base_model = TeacherFileBlock
    show_in_index = False


@admin.register(TextQuestion)
class TextQuestionAdmin(BaseBlockChildAdmin):
    base_model = TextQuestion
    show_in_index = False


class ChoiceAnswerInline(admin.TabularInline):
    model = ChoiceAnswer
    extra = 1
    fields = ("text", "is_correct")
    formset = None


class ChoiceAnswerInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        question = self.instance
        if not getattr(question, "max_choices", None):
            return

        correct_count = 0
        total_answers = 0
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            if form.cleaned_data.get("text"):
                total_answers += 1
            if form.cleaned_data.get("is_correct"):
                correct_count += 1

        if total_answers and correct_count == 0:
            raise ValidationError(
                "Нужно отметить хотя бы один правильный вариант ответа."
            )

        if correct_count > question.max_choices:
            raise ValidationError(
                "Слишком много правильных вариантов: "
                f"{correct_count} из {question.max_choices}."
            )


ChoiceAnswerInline.formset = ChoiceAnswerInlineFormSet


@admin.register(ChoiceQuestion)
class ChoiceQuestionAdmin(BaseBlockChildAdmin):
    base_model = ChoiceQuestion
    inlines = (ChoiceAnswerInline,)
    show_in_index = False


@admin.register(FileQuestion)
class FileQuestionAdmin(BaseBlockChildAdmin):
    base_model = FileQuestion
    show_in_index = False


@admin.register(Block)
class BlockParentAdmin(PolymorphicParentModelAdmin):
    base_model = Block
    child_models = (
        TextBlock,
        ImageBlock,
        VideoBlock,
        AudioBlock,
        TeacherFileBlock,
        TextQuestion,
        ChoiceQuestion,
        FileQuestion,
    )
    list_display = ("__str__", "lesson", "course_name", "order")
    list_filter = ("lesson__course", PolymorphicChildModelFilter)
    search_fields = ("lesson__name", "lesson__course__name")
    ordering = ("lesson__course", "lesson", "order")

    @admin.display(description="Курс", ordering="lesson__course__name")
    def course_name(self, obj):
        return obj.lesson.course.name
