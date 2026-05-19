from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .block_registry import BLOCK_TYPES, get_block_type_label, get_block_type_slug
from .decorators import teacher_required
from .forms import (
    CourseForm,
    LessonForm,
    build_choice_answer_formset,
)
from .models import Block, Course, Lesson


def _get_teacher_course(user, course_id):
    return get_object_or_404(Course, pk=course_id, author=user)


def _get_teacher_lesson(user, course_id, lesson_id):
    course = _get_teacher_course(user, course_id)
    lesson = get_object_or_404(Lesson, pk=lesson_id, course=course)
    return course, lesson


def _get_teacher_block(user, course_id, lesson_id, block_id):
    course, lesson = _get_teacher_lesson(user, course_id, lesson_id)
    block = get_object_or_404(Block, pk=block_id, lesson=lesson)
    return course, lesson, block.get_real_instance()


@teacher_required
def teacher_course_list(request):
    courses = (
        Course.objects.filter(author=request.user)
        .select_related("category")
        .prefetch_related("lessons")
        .order_by("-created_at")
    )
    return render(
        request,
        "lessons/teaching/course_list.html",
        {"courses": courses},
    )


@teacher_required
def teacher_course_create(request):
    if request.method == "POST":
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.author = request.user
            course.save()
            messages.success(request, f"Курс «{course.name}» создан.")
            return redirect("lessons:teacher_course_edit", course_id=course.pk)
    else:
        form = CourseForm(initial={"is_published": False})

    return render(
        request,
        "lessons/teaching/course_form.html",
        {"form": form, "title": "Новый курс", "is_edit": False},
    )


@teacher_required
def teacher_course_edit(request, course_id):
    course = _get_teacher_course(request.user, course_id)
    lessons = course.lessons.all()

    if request.method == "POST":
        form = CourseForm(request.POST, request.FILES, instance=course, is_edit=True)
        if form.is_valid():
            form.save()
            messages.success(request, "Курс сохранён.")
            return redirect("lessons:teacher_course_edit", course_id=course.pk)
    else:
        form = CourseForm(instance=course, is_edit=True)

    return render(
        request,
        "lessons/teaching/course_edit.html",
        {"form": form, "course": course, "lessons": lessons},
    )


@teacher_required
@require_POST
def teacher_course_delete(request, course_id):
    course = _get_teacher_course(request.user, course_id)
    name = course.name
    course.delete()
    messages.success(request, f"Курс «{name}» удалён.")
    return redirect("lessons:teacher_course_list")


@teacher_required
def teacher_lesson_create(request, course_id):
    course = _get_teacher_course(request.user, course_id)

    if request.method == "POST":
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.save()
            messages.success(request, f"Урок «{lesson.name}» добавлен.")
            return redirect(
                "lessons:teacher_lesson_editor",
                course_id=course.pk,
                lesson_id=lesson.pk,
            )
    else:
        form = LessonForm()

    return render(
        request,
        "lessons/teaching/lesson_form.html",
        {"form": form, "course": course, "title": "Новый урок"},
    )


@teacher_required
def teacher_lesson_edit(request, course_id, lesson_id):
    return redirect(
        "lessons:teacher_lesson_editor",
        course_id=course_id,
        lesson_id=lesson_id,
    )


@teacher_required
def teacher_lesson_editor(request, course_id, lesson_id):
    course, lesson = _get_teacher_lesson(request.user, course_id, lesson_id)
    blocks = [
        {"block": block, "type_label": get_block_type_label(block)}
        for block in lesson.blocks.all()
    ]

    if request.method == "POST":
        form = LessonForm(request.POST, instance=lesson)
        if form.is_valid():
            form.save()
            messages.success(request, "Название урока сохранено.")
            return redirect(
                "lessons:teacher_lesson_editor",
                course_id=course.pk,
                lesson_id=lesson.pk,
            )
    else:
        form = LessonForm(instance=lesson)

    return render(
        request,
        "lessons/teaching/lesson_editor.html",
        {
            "course": course,
            "lesson": lesson,
            "lesson_form": form,
            "blocks": blocks,
            "block_types": BLOCK_TYPES,
        },
    )


@teacher_required
def teacher_block_create(request, course_id, lesson_id, block_type):
    course, lesson = _get_teacher_lesson(request.user, course_id, lesson_id)
    config = BLOCK_TYPES.get(block_type)
    if not config:
        messages.error(request, "Неизвестный тип блока.")
        return redirect(
            "lessons:teacher_lesson_editor",
            course_id=course.pk,
            lesson_id=lesson.pk,
        )

    form_class = config["form"]
    is_choice = block_type == "choice_question"

    if request.method == "POST":
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    block = form.save(commit=False)
                    block.lesson = lesson
                    block.save()
                    if is_choice:
                        formset = build_choice_answer_formset(
                            data=request.POST, instance=block
                        )
                        if not formset.is_valid():
                            raise ValidationError(
                                "; ".join(
                                    e for err in formset.non_form_errors() for e in err
                                )
                                or "Проверьте варианты ответа."
                            )
                        formset.save()
                        block.clean()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
                formset = (
                    build_choice_answer_formset(data=request.POST)
                    if is_choice
                    else None
                )
            else:
                messages.success(request, "Блок добавлен.")
                return redirect(
                    "lessons:teacher_lesson_editor",
                    course_id=course.pk,
                    lesson_id=lesson.pk,
                )
        else:
            formset = (
                build_choice_answer_formset(data=request.POST) if is_choice else None
            )
    else:
        form = form_class()
        formset = build_choice_answer_formset() if is_choice else None

    return render(
        request,
        "lessons/teaching/block_form.html",
        {
            "course": course,
            "lesson": lesson,
            "form": form,
            "formset": formset,
            "block_type": block_type,
            "block_label": config["label"],
            "is_edit": False,
        },
    )


@teacher_required
def teacher_block_edit(request, course_id, lesson_id, block_id):
    course, lesson, block = _get_teacher_block(
        request.user, course_id, lesson_id, block_id
    )
    block_type = get_block_type_slug(block)
    config = BLOCK_TYPES.get(block_type)
    if not config:
        messages.error(request, "Этот тип блока не поддерживается.")
        return redirect(
            "lessons:teacher_lesson_editor",
            course_id=course.pk,
            lesson_id=lesson.pk,
        )

    form_class = config["form"]
    is_choice = block_type == "choice_question"

    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=block)
        formset = (
            build_choice_answer_formset(data=request.POST, instance=block)
            if is_choice
            else None
        )
        if form.is_valid() and (formset is None or formset.is_valid()):
            try:
                with transaction.atomic():
                    form.save()
                    if formset is not None:
                        formset.save()
                        block.refresh_from_db()
                        block.clean()
            except ValidationError as exc:
                messages.error(request, "".join(exc.messages))
            else:
                messages.success(request, "Блок сохранён.")
                return redirect(
                    "lessons:teacher_lesson_editor",
                    course_id=course.pk,
                    lesson_id=lesson.pk,
                )
    else:
        form = form_class(instance=block)
        formset = build_choice_answer_formset(instance=block) if is_choice else None

    return render(
        request,
        "lessons/teaching/block_form.html",
        {
            "course": course,
            "lesson": lesson,
            "block": block,
            "form": form,
            "formset": formset,
            "block_type": block_type,
            "block_label": config["label"],
            "is_edit": True,
        },
    )


@teacher_required
@require_POST
def teacher_block_delete(request, course_id, lesson_id, block_id):
    course, lesson, block = _get_teacher_block(
        request.user, course_id, lesson_id, block_id
    )
    label = get_block_type_label(block)
    block.delete()
    messages.success(request, f"Блок «{label}» удалён.")
    return redirect(
        "lessons:teacher_lesson_editor",
        course_id=course.pk,
        lesson_id=lesson.pk,
    )


@teacher_required
@require_POST
def teacher_block_move(request, course_id, lesson_id, block_id, direction):
    course, lesson = _get_teacher_lesson(request.user, course_id, lesson_id)
    block = get_object_or_404(Block, pk=block_id, lesson=lesson)
    delta = -1 if direction == "up" else 1
    neighbor = (
        Block.objects.filter(lesson=lesson, order=block.order + delta)
        .order_by("order")
        .first()
    )
    if neighbor:
        block.order, neighbor.order = neighbor.order, block.order
        block.save(update_fields=["order"])
        neighbor.save(update_fields=["order"])
    return redirect(
        "lessons:teacher_lesson_editor",
        course_id=course.pk,
        lesson_id=lesson.pk,
    )


@teacher_required
@require_POST
def teacher_lesson_move(request, course_id, lesson_id, direction):
    course = _get_teacher_course(request.user, course_id)
    lesson = get_object_or_404(Lesson, pk=lesson_id, course=course)
    delta = -1 if direction == "up" else 1
    neighbor = (
        Lesson.objects.filter(course=course, order=lesson.order + delta)
        .order_by("order")
        .first()
    )
    if neighbor:
        lesson.order, neighbor.order = neighbor.order, lesson.order
        lesson.save(update_fields=["order"])
        neighbor.save(update_fields=["order"])
    return redirect("lessons:teacher_course_edit", course_id=course.pk)


@teacher_required
@require_POST
def teacher_lesson_delete(request, course_id, lesson_id):
    course = _get_teacher_course(request.user, course_id)
    lesson = get_object_or_404(Lesson, pk=lesson_id, course=course)
    name = lesson.name
    lesson.delete()
    messages.success(request, f"Урок «{name}» удалён.")
    return redirect("lessons:teacher_course_edit", course_id=course.pk)
