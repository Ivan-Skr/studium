from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Block,
    ChoiceAnswerSelection,
    ChoiceAnswerSubmission,
    ChoiceQuestion,
    Course,
    FileAnswerSubmission,
    FileQuestion,
    Lesson,
    TextAnswerSubmission,
    TextQuestion,
)


def catalog(request):
    courses = (
        Course.objects.filter(is_published=True)
        .select_related("author", "category")
        .order_by("-created_at")
    )
    query = request.GET.get("q", "").strip()
    if query:
        courses = courses.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
    return render(request, "lessons/catalog.html", {"courses": courses})


def course_detail(request, course_id):
    queryset = Course.objects.select_related("author", "category")
    if request.user.is_authenticated:
        queryset = queryset.filter(
            Q(pk=course_id) & (Q(is_published=True) | Q(author=request.user))
        )
    else:
        queryset = queryset.filter(pk=course_id, is_published=True)
    course = get_object_or_404(queryset)
    lessons = course.lessons.all()
    return render(
        request,
        "lessons/course_detail.html",
        {"course": course, "lessons": lessons},
    )


def _get_published_lesson(course_id, lesson_id, user=None):
    course_qs = Course.objects.filter(pk=course_id)
    if user and user.is_authenticated:
        course_qs = course_qs.filter(Q(is_published=True) | Q(author=user))
    else:
        course_qs = course_qs.filter(is_published=True)
    course = get_object_or_404(course_qs)
    lesson = get_object_or_404(
        Lesson.objects.prefetch_related("blocks"),
        pk=lesson_id,
        course=course,
    )
    return course, lesson


def _get_block_in_lesson(course_id, lesson_id, block_id):
    course, lesson = _get_published_lesson(course_id, lesson_id)
    block = get_object_or_404(Block, pk=block_id, lesson=lesson)
    return course, lesson, block


def _lesson_navigation(course, lesson):
    lesson_list = list(course.lessons.all())
    current_index = next(
        (i for i, item in enumerate(lesson_list) if item.pk == lesson.pk),
        None,
    )
    prev_lesson = (
        lesson_list[current_index - 1]
        if current_index is not None and current_index > 0
        else None
    )
    next_lesson = (
        lesson_list[current_index + 1]
        if current_index is not None and current_index < len(lesson_list) - 1
        else None
    )
    return prev_lesson, next_lesson


def _is_deadline_passed(deadline):
    return deadline is not None and timezone.now() > deadline


def _text_answer_is_correct(question, answer):
    return answer.strip().lower() == question.correct_answer.strip().lower()


def _choice_score_percent(question, selected_ids):
    correct_ids = set(
        question.answers.filter(is_correct=True).values_list("pk", flat=True)
    )
    if not correct_ids:
        return 0
    selected = set(selected_ids)
    if selected == correct_ids:
        return 100
    if not selected & correct_ids:
        return 0
    return round(100 * len(selected & correct_ids) / len(correct_ids))


def _build_block_states(user, blocks):
    states = {}
    if not user.is_authenticated:
        return states

    text_ids = [b.pk for b in blocks if isinstance(b, TextQuestion)]
    choice_ids = [b.pk for b in blocks if isinstance(b, ChoiceQuestion)]
    file_ids = [b.pk for b in blocks if isinstance(b, FileQuestion)]

    text_latest = {}
    for s in TextAnswerSubmission.objects.filter(
        student=user, question_id__in=text_ids
    ).order_by("question_id", "-submitted_at"):
        if s.question_id not in text_latest:
            text_latest[s.question_id] = s

    choice_latest = {}
    for s in (
        ChoiceAnswerSubmission.objects.filter(student=user, question_id__in=choice_ids)
        .prefetch_related("selections__answer")
        .order_by("question_id", "-submitted_at")
    ):
        if s.question_id not in choice_latest:
            choice_latest[s.question_id] = s

    file_counts = {
        row["question_id"]: row["count"]
        for row in FileAnswerSubmission.objects.filter(
            student=user, question_id__in=file_ids
        )
        .values("question_id")
        .annotate(count=Count("pk"))
    }
    file_latest = {}
    for s in FileAnswerSubmission.objects.filter(
        student=user, question_id__in=file_ids
    ).order_by("question_id", "-uploaded_at"):
        if s.question_id not in file_latest:
            file_latest[s.question_id] = s

    text_attempts = {
        row["question_id"]: row["count"]
        for row in TextAnswerSubmission.objects.filter(
            student=user, question_id__in=text_ids
        )
        .values("question_id")
        .annotate(count=Count("attempt", distinct=True))
    }
    choice_attempts = {
        row["question_id"]: row["count"]
        for row in ChoiceAnswerSubmission.objects.filter(
            student=user, question_id__in=choice_ids
        )
        .values("question_id")
        .annotate(count=Count("attempt", distinct=True))
    }

    for block in blocks:
        state = {
            "can_submit": True,
            "submitted": False,
            "attempts_used": 0,
            "max_attempts": getattr(block, "max_attempts", None),
            "is_correct": None,
            "score": None,
            "last_answer": "",
            "uploaded_file": None,
            "error": None,
        }

        if isinstance(block, TextQuestion):
            state["attempts_used"] = text_attempts.get(block.pk, 0)
            submission = text_latest.get(block.pk)
            if submission:
                state["submitted"] = True
                state["last_answer"] = submission.answer
                state["is_correct"] = _text_answer_is_correct(block, submission.answer)
            if _is_deadline_passed(block.deadline):
                state["can_submit"] = False
            elif state["attempts_used"] >= block.max_attempts:
                state["can_submit"] = False

        elif isinstance(block, ChoiceQuestion):
            state["attempts_used"] = choice_attempts.get(block.pk, 0)
            submission = choice_latest.get(block.pk)
            if submission:
                state["submitted"] = True
                selected_ids = list(
                    submission.selections.values_list("answer_id", flat=True)
                )
                state["score"] = _choice_score_percent(block, selected_ids)
                state["is_correct"] = state["score"] == 100
            if _is_deadline_passed(block.deadline):
                state["can_submit"] = False
            elif state["attempts_used"] >= block.max_attempts:
                state["can_submit"] = False

        elif isinstance(block, FileQuestion):
            state["attempts_used"] = file_counts.get(block.pk, 0)
            submission = file_latest.get(block.pk)
            if submission:
                state["submitted"] = True
                state["uploaded_file"] = submission.file
            if _is_deadline_passed(block.deadline):
                state["can_submit"] = False
            elif state["attempts_used"] >= block.max_attempts:
                state["can_submit"] = False

        states[block.pk] = state

    return states


def _default_block_state():
    return {
        "can_submit": False,
        "submitted": False,
        "attempts_used": 0,
        "max_attempts": None,
        "is_correct": None,
        "score": None,
        "last_answer": "",
        "uploaded_file": None,
    }


def lesson_detail(request, course_id, lesson_id):
    course, lesson = _get_published_lesson(course_id, lesson_id, user=request.user)
    blocks = list(lesson.blocks.all())
    prev_lesson, next_lesson = _lesson_navigation(course, lesson)
    block_states = _build_block_states(request.user, blocks)
    blocks_with_state = [
        {
            "block": block,
            "state": block_states.get(block.pk, _default_block_state()),
        }
        for block in blocks
    ]

    return render(
        request,
        "lessons/lesson_view.html",
        {
            "course": course,
            "lesson": lesson,
            "blocks_with_state": blocks_with_state,
            "prev_lesson": prev_lesson,
            "next_lesson": next_lesson,
        },
    )


def _redirect_to_lesson(course_id, lesson_id):
    return redirect("lessons:lesson_detail", course_id=course_id, lesson_id=lesson_id)


@login_required(login_url=settings.LOGIN_URL)
@require_POST
def submit_text_answer(request, course_id, lesson_id, block_id):
    course, lesson, block = _get_block_in_lesson(course_id, lesson_id, block_id)
    if not isinstance(block, TextQuestion):
        messages.error(request, "Этот блок не является текстовым вопросом.")
        return _redirect_to_lesson(course_id, lesson_id)

    answer = request.POST.get("answer", "").strip()
    if not answer:
        messages.error(request, "Введите ответ.")
        return _redirect_to_lesson(course_id, lesson_id)

    if len(answer) > 100:
        messages.error(request, "Ответ слишком длинный (максимум 100 символов).")
        return _redirect_to_lesson(course_id, lesson_id)

    submission = TextAnswerSubmission(
        question=block,
        student=request.user,
        answer=answer,
    )
    try:
        submission.full_clean()
        submission.save()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return _redirect_to_lesson(course_id, lesson_id)

    if _text_answer_is_correct(block, answer):
        messages.success(request, "Верно!")
    else:
        messages.warning(
            request, "Ответ отправлен, но он неверный. Попробуйте ещё раз."
        )

    return _redirect_to_lesson(course_id, lesson_id)


@login_required(login_url=settings.LOGIN_URL)
@require_POST
def submit_choice_answer(request, course_id, lesson_id, block_id):
    course, lesson, block = _get_block_in_lesson(course_id, lesson_id, block_id)
    if not isinstance(block, ChoiceQuestion):
        messages.error(request, "Этот блок не является вопросом с выбором.")
        return _redirect_to_lesson(course_id, lesson_id)

    raw_ids = request.POST.getlist("answer")
    if not raw_ids:
        messages.error(request, "Выберите хотя бы один вариант.")
        return _redirect_to_lesson(course_id, lesson_id)

    try:
        selected_ids = [int(value) for value in raw_ids]
    except ValueError:
        messages.error(request, "Некорректный выбор ответа.")
        return _redirect_to_lesson(course_id, lesson_id)

    if len(selected_ids) > block.max_choices:
        messages.error(
            request,
            f"Можно выбрать не более {block.max_choices} вариант(ов).",
        )
        return _redirect_to_lesson(course_id, lesson_id)

    valid_ids = set(
        block.answers.filter(pk__in=selected_ids).values_list("pk", flat=True)
    )
    if len(valid_ids) != len(selected_ids):
        messages.error(request, "Выбраны недопустимые варианты ответа.")
        return _redirect_to_lesson(course_id, lesson_id)

    submission = ChoiceAnswerSubmission(question=block, student=request.user)
    try:
        with transaction.atomic():
            submission.full_clean()
            submission.save()
            for answer_id in selected_ids:
                ChoiceAnswerSelection.objects.create(
                    submission=submission,
                    answer_id=answer_id,
                )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return _redirect_to_lesson(course_id, lesson_id)

    score = _choice_score_percent(block, selected_ids)
    if score == 100:
        messages.success(request, f"Верно! Результат: {score}%")
    else:
        messages.warning(request, f"Результат: {score}%")

    return _redirect_to_lesson(course_id, lesson_id)


@login_required(login_url=settings.LOGIN_URL)
@require_POST
def submit_file_answer(request, course_id, lesson_id, block_id):
    course, lesson, block = _get_block_in_lesson(course_id, lesson_id, block_id)
    if not isinstance(block, FileQuestion):
        messages.error(request, "Этот блок не является заданием с файлом.")
        return _redirect_to_lesson(course_id, lesson_id)

    uploaded = request.FILES.get("file")
    if not uploaded:
        messages.error(request, "Выберите файл для загрузки.")
        return _redirect_to_lesson(course_id, lesson_id)

    submission = FileAnswerSubmission(
        question=block,
        student=request.user,
        file=uploaded,
    )
    try:
        submission.full_clean()
        submission.save()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return _redirect_to_lesson(course_id, lesson_id)

    messages.success(request, "Файл успешно отправлен.")
    return _redirect_to_lesson(course_id, lesson_id)
