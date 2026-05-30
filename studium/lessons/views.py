from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST
import calendar
from datetime import date

from .forms import EnrollmentCodeForm
from .models import (
    Block,
    ChoiceAnswerSelection,
    ChoiceAnswerSubmission,
    ChoiceQuestion,
    Course,
    CourseCompletion,
    CourseEnrollment,
    FileAnswerSubmission,
    FileQuestion,
    Lesson,
    LessonProgress,
    StudentCertificate,
    TextAnswerSubmission,
    TextQuestion,
    LessonStudyTime,
)

MAX_LEARNING_SECONDS_PER_PING = 120


def _calendar_escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _ics_datetime(value):
    return timezone.localtime(value).strftime("%Y%m%dT%H%M%S")


def _student_deadline_events(user):
    course_ids = CourseEnrollment.objects.filter(
        student=user,
        status=CourseEnrollment.Status.APPROVED,
    ).values_list("course_id", flat=True)

    lessons = (
        Lesson.objects.filter(
            course_id__in=course_ids,
            deadline__isnull=False,
        )
        .select_related("course")
        .order_by("deadline", "course__name", "order")
    )

    events = []
    for lesson in lessons:
        events.append(
            {
                "id": f"lesson-{lesson.pk}",
                "deadline": lesson.deadline,
                "course": lesson.course,
                "lesson": lesson,
                "kind": "Дедлайн урока",
                "title": lesson.name,
            }
        )

    return events

def _month_from_request(request):
    today = timezone.localdate()

    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if month < 1 or month > 12:
            raise ValueError
    except ValueError:
        year = today.year
        month = today.month

    return year, month

def _shift_month(year, month, delta):
    month += delta

    while month < 1:
        month += 12
        year -= 1

    while month > 12:
        month -= 12
        year += 1

    return year, month

def _build_calendar_grid(events, year, month):
    russian_months = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }

    first_day = date(year, month, 1)

    # Python weekday:
    # понедельник = 0, вторник = 1, ..., воскресенье = 6.
    # Поэтому календарь будет начинаться с понедельника.
    days_before = first_day.weekday()
    calendar_start = first_day - timezone.timedelta(days=days_before)

    events_by_date = {}
    for event in events:
        event_date = timezone.localtime(event["deadline"]).date()
        events_by_date.setdefault(event_date, []).append(event)

    weeks = []
    current_day = calendar_start

    for _ in range(6):
        week = []

        for _ in range(7):
            week.append(
                {
                    "date": current_day,
                    "day": current_day.day,
                    "in_current_month": current_day.month == month,
                    "is_today": current_day == timezone.localdate(),
                    "events": events_by_date.get(current_day, []),
                }
            )
            current_day = current_day + timezone.timedelta(days=1)

        weeks.append(week)

    prev_year, prev_month = _shift_month(year, month, -1)
    next_year, next_month = _shift_month(year, month, 1)

    return {
        "weeks": weeks,
        "month_label": f"{russian_months[month]} {year}",
        "year": year,
        "month": month,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
    }

def _calendar_feed_url(request, user):
    return request.build_absolute_uri(
        reverse("lessons:student_calendar_ics", args=[user.calendar_token])
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


@login_required(login_url=settings.LOGIN_URL)
def student_calendar(request):
    if not request.user.is_student:
        return redirect("lessons:catalog")

    events = _student_deadline_events(request.user)
    year, month = _month_from_request(request)
    calendar_grid = _build_calendar_grid(events, year, month)

    return render(
        request,
        "lessons/student_calendar.html",
        {
            "events": events,
            "calendar_grid": calendar_grid,
            "calendar_feed_url": _calendar_feed_url(request, request.user),
        },
    )


def student_calendar_ics(request, token):
    User = get_user_model()
    user = get_object_or_404(User, calendar_token=token, is_student=True)
    events = _student_deadline_events(user)
    now = timezone.now().strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Studium//Student Deadlines//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_calendar_escape('Studium: дедлайны')}",
    ]
    for event in events:
        lesson_url = request.build_absolute_uri(
            reverse(
                "lessons:lesson_detail",
                args=[event["course"].pk, event["lesson"].pk],
            )
        )
        starts_at = _ics_datetime(event["deadline"])
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{event['id']}@studium",
                f"DTSTAMP:{now}",
                f"DTSTART;TZID={settings.TIME_ZONE}:{starts_at}",
                f"DTEND;TZID={settings.TIME_ZONE}:{starts_at}",
                f"SUMMARY:{_calendar_escape(event['course'].name + ': ' + event['lesson'].name)}",
                f"DESCRIPTION:{_calendar_escape('Дедлайн урока · ' + event['course'].name)}",
                f"URL:{lesson_url}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")

    response = HttpResponse("\r\n".join(lines) + "\r\n", content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="studium-deadlines.ics"'
    return response


def course_detail(request, course_id):
    queryset = Course.objects.select_related("author", "category")
    if request.user.is_authenticated:
        queryset = queryset.filter(
            Q(pk=course_id) & (Q(is_published=True) | Q(author=request.user))
        )
    else:
        queryset = queryset.filter(pk=course_id, is_published=True)
    course = get_object_or_404(queryset)
    lessons = list(course.lessons.all())
    enrollment = None
    enrollment_form = None
    can_start_learning = False

    if request.user.is_authenticated:
        if request.user == course.author:
            can_start_learning = True
        else:
            enrollment = CourseEnrollment.objects.filter(
                course=course,
                student=request.user,
            ).first()
            can_start_learning = (
                enrollment is not None
                and enrollment.status == CourseEnrollment.Status.APPROVED
            )

    if (
        request.user.is_authenticated
        and not can_start_learning
        and course.requires_enrollment_code
        and (
            enrollment is None or enrollment.status == CourseEnrollment.Status.REJECTED
        )
    ):
        enrollment_form = EnrollmentCodeForm(course=course)

    if request.user.is_authenticated:
        progress_by_lesson_id = {
            progress.lesson_id: progress
            for progress in LessonProgress.objects.filter(
                student=request.user,
                lesson__in=lessons,
            )
        }
        for lesson in lessons:
            progress = progress_by_lesson_id.get(lesson.pk)
            lesson.student_score_percent = (
                progress.score_percent if progress is not None else None
            )
            lesson.student_is_completed = progress is not None
    else:
        for lesson in lessons:
            lesson.student_score_percent = None
            lesson.student_is_completed = False

    return render(
        request,
        "lessons/course_detail.html",
        {
            "course": course,
            "lessons": lessons,
            "enrollment": enrollment,
            "enrollment_form": enrollment_form,
            "can_start_learning": can_start_learning,
        },
    )


@login_required(login_url=settings.LOGIN_URL)
@require_POST
def enroll_course(request, course_id):
    course = get_object_or_404(Course.objects.filter(pk=course_id, is_published=True))
    if request.user == course.author:
        messages.info(request, "Вы являетесь автором этого курса.")
        return redirect("lessons:course_detail", course_id=course.pk)

    enrollment = CourseEnrollment.objects.filter(
        course=course,
        student=request.user,
    ).first()
    if enrollment and enrollment.status == CourseEnrollment.Status.APPROVED:
        messages.info(request, "Вы уже записаны на этот курс.")
        return redirect("lessons:course_detail", course_id=course.pk)
    if enrollment and enrollment.status == CourseEnrollment.Status.PENDING:
        messages.info(request, "Ваша заявка уже отправлена преподавателю.")
        return redirect("lessons:course_detail", course_id=course.pk)

    if course.requires_enrollment_code:
        form = EnrollmentCodeForm(request.POST, course=course)
        if not form.is_valid():
            messages.error(request, "Неверное кодовое слово.")
            return redirect("lessons:course_detail", course_id=course.pk)
        status = CourseEnrollment.Status.PENDING
        success_message = "Заявка отправлена преподавателю."
    else:
        status = CourseEnrollment.Status.APPROVED
        success_message = "Вы записались на курс."

    if enrollment:
        enrollment.status = status
        enrollment.save(update_fields=["status", "updated_at"])
    else:
        CourseEnrollment.objects.create(
            course=course,
            student=request.user,
            status=status,
        )
    messages.success(request, success_message)
    return redirect("lessons:course_detail", course_id=course.pk)


def _user_can_learn_course(user, course):
    if user is None:
        return False
    if not user.is_authenticated:
        return False
    if user == course.author:
        return True
    return CourseEnrollment.objects.filter(
        course=course,
        student=user,
        status=CourseEnrollment.Status.APPROVED,
    ).exists()


def _get_published_lesson(course_id, lesson_id, user=None):
    course_qs = Course.objects.filter(pk=course_id)
    if user and user.is_authenticated:
        course_qs = course_qs.filter(Q(is_published=True) | Q(author=user))
    else:
        course_qs = course_qs.filter(is_published=True)
    course = get_object_or_404(course_qs)
    if not _user_can_learn_course(user, course):
        get_object_or_404(Course.objects.none())
    lesson = get_object_or_404(
        Lesson.objects.prefetch_related("blocks"),
        pk=lesson_id,
        course=course,
    )
    return course, lesson


def _get_block_in_lesson(course_id, lesson_id, block_id, user=None):
    course, lesson = _get_published_lesson(course_id, lesson_id, user=user)
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


def _choice_selected_ids(submission):
    if submission is None:
        return []
    return list(submission.selections.values_list("answer_id", flat=True))


def _parse_choice_selected_ids(request, question):
    raw_ids = request.POST.getlist(f"choice_{question.pk}")
    if not raw_ids:
        raise ValidationError(f"Выберите ответ: {question.question}")

    try:
        selected_ids = list(dict.fromkeys(int(value) for value in raw_ids))
    except ValueError:
        raise ValidationError(f"Некорректный выбор ответа: {question.question}")

    if len(selected_ids) > question.max_choices:
        raise ValidationError(
            f"Можно выбрать не более {question.max_choices} вариант(ов): "
            f"{question.question}"
        )

    valid_ids = set(
        question.answers.filter(pk__in=selected_ids).values_list("pk", flat=True)
    )
    if len(valid_ids) != len(selected_ids):
        raise ValidationError(f"Выбраны недопустимые варианты: {question.question}")

    return selected_ids


def _save_choice_submission(question, student, selected_ids):
    submission = ChoiceAnswerSubmission(question=question, student=student)
    submission.full_clean()
    submission.save()
    for answer_id in selected_ids:
        ChoiceAnswerSelection.objects.create(
            submission=submission,
            answer_id=answer_id,
        )
    return submission


def _question_blocks(blocks):
    return [
        block
        for block in blocks
        if isinstance(block, (TextQuestion, ChoiceQuestion, FileQuestion))
    ]


def _lesson_progress(user, lesson):
    if not user.is_authenticated:
        return None
    return LessonProgress.objects.filter(lesson=lesson, student=user).first()


def _block_score_percent(user, block):
    if isinstance(block, TextQuestion):
        latest = (
            TextAnswerSubmission.objects.filter(student=user, question=block)
            .order_by("-submitted_at")
            .first()
        )
        return 100 if latest and _text_answer_is_correct(block, latest.answer) else 0

    if isinstance(block, ChoiceQuestion):
        latest = (
            ChoiceAnswerSubmission.objects.filter(student=user, question=block)
            .prefetch_related("selections")
            .order_by("-submitted_at")
            .first()
        )
        return _choice_score_percent(block, _choice_selected_ids(latest))

    if isinstance(block, FileQuestion):
        return (
            100
            if FileAnswerSubmission.objects.filter(
                student=user,
                question=block,
            ).exists()
            else 0
        )

    return None


def _lesson_score_percent(user, blocks):
    if not user.is_authenticated:
        return None

    scores = [
        _block_score_percent(user, block)
        for block in _question_blocks(blocks)
    ]
    scores = [score for score in scores if score is not None]
    if not scores:
        return 100
    return round(sum(scores) / len(scores))


def _lesson_attempt_summary(block_states, blocks):
    used_values = []
    max_values = []
    for block in _question_blocks(blocks):
        state = block_states.get(block.pk)
        if not state:
            continue
        used_values.append(state["attempts_used"])
        if state["max_attempts"] is not None:
            max_values.append(state["max_attempts"])
    return {
        "used": max(used_values) if used_values else 0,
        "max": max(max_values) if max_values else 0,
    }


def _choice_questions_all_correct(user, blocks):
    choice_blocks = [block for block in blocks if isinstance(block, ChoiceQuestion)]
    return bool(choice_blocks) and all(
        _block_score_percent(user, block) == 100 for block in choice_blocks
    )


def _issue_certificate_from_template(template, student):
    image = template.image.name if template.image else ""
    certificate, created = StudentCertificate.objects.get_or_create(
        template=template,
        student=student,
        defaults={
            "course": template.course,
            "title": template.title,
            "description": template.description,
            "image": image,
            "is_completion_certificate": template.is_completion_certificate,
        },
    )
    if not created:
        certificate.course = template.course
        certificate.title = template.title
        certificate.description = template.description
        certificate.image = image
        certificate.is_completion_certificate = template.is_completion_certificate
        certificate.save(
            update_fields=[
                "course",
                "title",
                "description",
                "image",
                "is_completion_certificate",
            ]
        )
    return certificate


def _ensure_course_completion(course, student):
    lesson_ids = list(course.lessons.values_list("pk", flat=True))
    if not lesson_ids:
        return None

    completed_count = LessonProgress.objects.filter(
        student=student,
        lesson_id__in=lesson_ids,
    ).count()
    if completed_count != len(lesson_ids):
        return None

    completion, _ = CourseCompletion.objects.get_or_create(
        course=course,
        student=student,
    )
    template = course.certificate_templates.filter(
        is_completion_certificate=True
    ).first()
    if template:
        _issue_certificate_from_template(template, student)
    return completion


def _lesson_assignment_state(user, lesson, blocks):
    if not user.is_authenticated:
        return {
            "is_completed": False,
            "can_complete": False,
            "has_assignments": False,
            "score_percent": None,
        }

    progress = _lesson_progress(user, lesson)
    is_completed = progress is not None
    score_percent = (
        progress.score_percent
        if progress is not None
        else _lesson_score_percent(user, blocks)
    )
    question_blocks = _question_blocks(blocks)
    if not question_blocks:
        return {
            "is_completed": is_completed,
            "can_complete": not is_completed,
            "has_assignments": False,
            "score_percent": score_percent,
        }

    for block in question_blocks:
        if isinstance(block, TextQuestion):
            latest = (
                TextAnswerSubmission.objects.filter(student=user, question=block)
                .order_by("-submitted_at")
                .first()
            )
            if latest is None:
                return {
                    "is_completed": is_completed,
                    "can_complete": False,
                    "has_assignments": True,
                    "score_percent": score_percent,
                }
        elif isinstance(block, ChoiceQuestion):
            latest = (
                ChoiceAnswerSubmission.objects.filter(student=user, question=block)
                .prefetch_related("selections")
                .order_by("-submitted_at")
                .first()
            )
            if latest is None:
                return {
                    "is_completed": is_completed,
                    "can_complete": False,
                    "has_assignments": True,
                    "score_percent": score_percent,
                }
        elif isinstance(block, FileQuestion):
            if not FileAnswerSubmission.objects.filter(
                student=user,
                question=block,
            ).exists():
                return {
                    "is_completed": is_completed,
                    "can_complete": False,
                    "has_assignments": True,
                    "score_percent": score_percent,
                }

    return {
        "is_completed": is_completed,
        "can_complete": not is_completed,
        "has_assignments": True,
        "score_percent": score_percent,
    }


def _build_block_states(user, blocks, lesson=None):
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
            "selected_ids": [],
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
            if lesson is not None and _is_deadline_passed(lesson.deadline):
                state["can_submit"] = False
            elif state["attempts_used"] >= block.max_attempts:
                state["can_submit"] = False

        elif isinstance(block, ChoiceQuestion):
            state["attempts_used"] = choice_attempts.get(block.pk, 0)
            submission = choice_latest.get(block.pk)
            if submission:
                state["submitted"] = True
                selected_ids = _choice_selected_ids(submission)
                state["selected_ids"] = selected_ids
                state["score"] = _choice_score_percent(block, selected_ids)
                state["is_correct"] = state["score"] == 100
            if lesson is not None and _is_deadline_passed(lesson.deadline):
                state["can_submit"] = False
            elif state["attempts_used"] >= block.max_attempts:
                state["can_submit"] = False

        elif isinstance(block, FileQuestion):
            state["attempts_used"] = file_counts.get(block.pk, 0)
            submission = file_latest.get(block.pk)
            if submission:
                state["submitted"] = True
                state["uploaded_file"] = submission.file
            if lesson is not None and _is_deadline_passed(lesson.deadline):
                state["can_submit"] = False
            elif state["attempts_used"] >= block.max_attempts:
                state["can_submit"] = False

        states[block.pk] = state

    if lesson is not None and _lesson_progress(user, lesson):
        for state in states.values():
            state["can_submit"] = False

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
        "selected_ids": [],
        "uploaded_file": None,
    }


def lesson_detail(request, course_id, lesson_id):
    course, lesson = _get_published_lesson(course_id, lesson_id, user=request.user)
    blocks = list(lesson.blocks.all())
    prev_lesson, next_lesson = _lesson_navigation(course, lesson)
    block_states = _build_block_states(request.user, blocks, lesson)
    lesson_state = _lesson_assignment_state(request.user, lesson, blocks)
    blocks_with_state = [
        {
            "block": block,
            "state": block_states.get(block.pk, _default_block_state()),
        }
        for block in blocks
    ]
    has_choice_questions = any(isinstance(block, ChoiceQuestion) for block in blocks)
    can_check_choices = request.user.is_authenticated and any(
        isinstance(block, ChoiceQuestion)
        and block_states.get(block.pk, _default_block_state())["can_submit"]
        for block in blocks
    ) and not _choice_questions_all_correct(request.user, blocks)
    attempt_summary = _lesson_attempt_summary(block_states, blocks)

    return render(
        request,
        "lessons/lesson_view.html",
        {
            "course": course,
            "lesson": lesson,
            "blocks_with_state": blocks_with_state,
            "prev_lesson": prev_lesson,
            "next_lesson": next_lesson,
            "lesson_state": lesson_state,
            "has_choice_questions": has_choice_questions,
            "can_check_choices": can_check_choices,
            "attempt_summary": attempt_summary,
        },
    )


def _redirect_to_lesson(course_id, lesson_id):
    return redirect("lessons:lesson_detail", course_id=course_id, lesson_id=lesson_id)


@login_required(login_url=settings.LOGIN_URL)
@require_POST
def track_learning_time(request, course_id, lesson_id):
    course, lesson = _get_published_lesson(course_id, lesson_id, user=request.user)
    try:
        seconds = int(request.POST.get("seconds", "0"))
    except ValueError:
        seconds = 0
    seconds = max(0, min(seconds, MAX_LEARNING_SECONDS_PER_PING))

    if seconds:
        request.user.__class__.objects.filter(pk=request.user.pk).update(
            learning_seconds=F("learning_seconds") + seconds
        )
        LessonStudyTime.objects.update_or_create(
            lesson=lesson,
            student=request.user,
            defaults={},
        )
        LessonStudyTime.objects.filter(
            lesson=lesson,
            student=request.user,
        ).update(seconds=F("seconds") + seconds)
    return HttpResponse(status=204)





@login_required(login_url=settings.LOGIN_URL)
@require_POST
def complete_lesson(request, course_id, lesson_id):
    course, lesson = _get_published_lesson(course_id, lesson_id, user=request.user)
    blocks = list(lesson.blocks.all())
    lesson_state = _lesson_assignment_state(request.user, lesson, blocks)
    if lesson_state["is_completed"]:
        messages.info(request, "Урок уже завершен.")
        return _redirect_to_lesson(course_id, lesson_id)
    if not lesson_state["can_complete"]:
        messages.warning(request, "Выполните все задания.")
        return _redirect_to_lesson(course_id, lesson_id)

    score_percent = _lesson_score_percent(request.user, blocks)
    LessonProgress.objects.update_or_create(
        lesson=lesson,
        student=request.user,
        defaults={"score_percent": score_percent},
    )
    completion = _ensure_course_completion(course, request.user)
    if completion:
        messages.success(request, "Курс завершен.")
    else:
        messages.success(request, "Урок засчитан.")
    return _redirect_to_lesson(course_id, lesson_id)


@login_required(login_url=settings.LOGIN_URL)
@require_POST
def submit_text_answer(request, course_id, lesson_id, block_id):
    course, lesson, block = _get_block_in_lesson(
        course_id, lesson_id, block_id, user=request.user
    )
    if _lesson_progress(request.user, lesson):
        messages.warning(request, "Урок уже завершен.")
        return _redirect_to_lesson(course_id, lesson_id)
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
def submit_lesson_choice_answers(request, course_id, lesson_id):
    course, lesson = _get_published_lesson(course_id, lesson_id, user=request.user)
    if _lesson_progress(request.user, lesson):
        messages.warning(request, "Урок уже завершен.")
        return _redirect_to_lesson(course_id, lesson_id)
    if _choice_questions_all_correct(request.user, lesson.blocks.all()):
        messages.info(request, "Все ответы уже верны.")
        return _redirect_to_lesson(course_id, lesson_id)
    choice_blocks = [
        block for block in lesson.blocks.all() if isinstance(block, ChoiceQuestion)
    ]
    if not choice_blocks:
        messages.info(request, "В уроке нет вопросов с выбором ответа.")
        return _redirect_to_lesson(course_id, lesson_id)

    prepared = []
    errors = []
    for block in choice_blocks:
        latest = (
            ChoiceAnswerSubmission.objects.filter(student=request.user, question=block)
            .prefetch_related("selections")
            .order_by("-submitted_at")
            .first()
        )
        latest_score = _choice_score_percent(block, _choice_selected_ids(latest))
        attempts_used = (
            ChoiceAnswerSubmission.objects.filter(
                student=request.user,
                question=block,
            )
            .values("attempt")
            .distinct()
            .count()
        )

        if _is_deadline_passed(lesson.deadline) or attempts_used >= block.max_attempts:
            if latest_score != 100:
                errors.append(f"Нельзя проверить вопрос: {block.question}")
            continue

        try:
            selected_ids = _parse_choice_selected_ids(request, block)
        except ValidationError as exc:
            errors.extend(exc.messages)
            continue
        prepared.append((block, selected_ids))

    if errors:
        messages.error(request, "; ".join(errors))
        return _redirect_to_lesson(course_id, lesson_id)

    if not prepared:
        messages.info(request, "Нет вопросов для проверки.")
        return _redirect_to_lesson(course_id, lesson_id)

    try:
        with transaction.atomic():
            for block, selected_ids in prepared:
                _save_choice_submission(block, request.user, selected_ids)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return _redirect_to_lesson(course_id, lesson_id)

    correct_count = sum(
        1
        for block, selected_ids in prepared
        if _choice_score_percent(block, selected_ids) == 100
    )
    total_count = len(prepared)
    if correct_count == total_count:
        messages.success(request, "Проверка выполнена: все ответы верны.")
    else:
        messages.warning(
            request,
            f"Проверка выполнена: верно {correct_count} из {total_count}.",
        )

    return _redirect_to_lesson(course_id, lesson_id)


@login_required(login_url=settings.LOGIN_URL)
@require_POST
def submit_file_answer(request, course_id, lesson_id, block_id):
    course, lesson, block = _get_block_in_lesson(
        course_id, lesson_id, block_id, user=request.user
    )
    if _lesson_progress(request.user, lesson):
        messages.warning(request, "Урок уже завершен.")
        return _redirect_to_lesson(course_id, lesson_id)
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


