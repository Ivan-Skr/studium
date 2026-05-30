from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from django.urls import reverse

from .block_registry import BLOCK_TYPES, get_block_type_label, get_block_type_slug
from .decorators import teacher_required
from .forms import (
    CertificateTemplateForm,
    CourseForm,
    LessonForm,
    build_choice_answer_formset,
)
from .models import (
    Block,
    CertificateTemplate,
    Course,
    CourseEnrollment,
    Lesson,
    StudentCertificate,
    ChoiceQuestion,
    LessonProgress,
    LessonStudyTime,
    StudentGroup,
    TextQuestion,
    FileQuestion,
)


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
    dashboard = _teacher_courses_dashboard(request.user)

    active_course = None
    student_rows = []
    groups = []
    progress_table = None
    active_modal = None
    selected_group_id = request.GET.get("group") or ""

    # ВАЖНО: значения по умолчанию, чтобы /teaching/ открывался без ошибки
    students_average_progress = 0
    students_completed_count = 0

    course_id = (
        request.GET.get("students")
        or request.GET.get("groups")
        or request.GET.get("progress")
    )

    if course_id:
        active_course = _get_teacher_course(request.user, course_id)
        groups = active_course.student_groups.all().prefetch_related(
            "enrollments__student"
        )

        if request.GET.get("students"):
            active_modal = "students"
            student_rows = _course_student_rows(
                active_course,
                group_id=selected_group_id if selected_group_id else None,
            )

            if student_rows:
                students_average_progress = round(
                    sum(row["progress_percent"] for row in student_rows)
                    / len(student_rows)
                )

            students_completed_count = sum(
                1 for row in student_rows if row["is_completed"]
            )

        elif request.GET.get("groups"):
            active_modal = "groups"
            student_rows = _course_student_rows(active_course)

        elif request.GET.get("progress"):
            active_modal = "progress"
            progress_table = _course_progress_table(
                active_course,
                group_id=selected_group_id if selected_group_id else None,
            )

    return render(
        request,
        "lessons/teaching/course_list.html",
        {
            **dashboard,
            "active_course": active_course,
            "active_modal": active_modal,
            "student_rows": student_rows,
            "groups": groups,
            "progress_table": progress_table,
            "selected_group_id": selected_group_id,
            "students_average_progress": students_average_progress,
            "students_completed_count": students_completed_count,
        },
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
    certificate_templates = course.certificate_templates.all()
    certificate_form = CertificateTemplateForm(course=course)
    enrolled_students = [
        enrollment.student
        for enrollment in course.enrollments.filter(
            status=CourseEnrollment.Status.APPROVED
        ).select_related("student")
    ]
    certificate_cards = []
    for template in certificate_templates:
        selected_student_ids = set(
            template.student_certificates.values_list("student_id", flat=True)
        )
        certificate_cards.append(
            {
                "template": template,
                "selected_student_ids": selected_student_ids,
                "form": CertificateTemplateForm(instance=template, course=course),
            }
        )
    enrollment_requests = (
        course.enrollments.filter(status=CourseEnrollment.Status.PENDING)
        .select_related("student")
        .order_by("requested_at")
    )

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
        {
            "form": form,
            "course": course,
            "lessons": lessons,
            "enrollment_requests": enrollment_requests,
            "certificate_templates": certificate_templates,
            "certificate_cards": certificate_cards,
            "certificate_form": certificate_form,
            "enrolled_students": enrolled_students,
        },
    )


def _copy_certificate_fields(template, student):
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


@teacher_required
@require_POST
def teacher_certificate_create(request, course_id):
    course = _get_teacher_course(request.user, course_id)
    form = CertificateTemplateForm(request.POST, request.FILES, course=course)
    if form.is_valid():
        certificate = form.save(commit=False)
        certificate.course = course
        certificate.save()
        if certificate.is_completion_certificate:
            for completion in course.completions.select_related("student"):
                _copy_certificate_fields(certificate, completion.student)
        messages.success(request, "Сертификат создан.")
    else:
        messages.error(request, "Проверьте данные сертификата.")
    return redirect("lessons:teacher_course_edit", course_id=course.pk)


@teacher_required
@require_POST
def teacher_certificate_update(request, course_id, certificate_id):
    course = _get_teacher_course(request.user, course_id)
    certificate = get_object_or_404(
        CertificateTemplate, pk=certificate_id, course=course
    )
    form = CertificateTemplateForm(
        request.POST,
        request.FILES,
        instance=certificate,
        course=course,
    )
    if form.is_valid():
        certificate = form.save()
        for issued in certificate.student_certificates.all():
            _copy_certificate_fields(certificate, issued.student)
        messages.success(request, "Сертификат сохранен.")
    else:
        messages.error(request, "Проверьте данные сертификата.")
    return redirect("lessons:teacher_course_edit", course_id=course.pk)


@teacher_required
@require_POST
def teacher_certificate_delete(request, course_id, certificate_id):
    course = _get_teacher_course(request.user, course_id)
    certificate = get_object_or_404(
        CertificateTemplate, pk=certificate_id, course=course
    )
    certificate.student_certificates.update(template=None)
    certificate.delete()
    messages.success(
        request, "Сертификат удален. У студентов уже выданные сертификаты сохранены."
    )
    return redirect("lessons:teacher_course_edit", course_id=course.pk)


@teacher_required
@require_POST
def teacher_certificate_assign(request, course_id, certificate_id):
    course = _get_teacher_course(request.user, course_id)
    certificate = get_object_or_404(
        CertificateTemplate, pk=certificate_id, course=course
    )
    selected_ids = {
        int(value) for value in request.POST.getlist("students") if value.isdigit()
    }
    allowed_ids = set(
        course.enrollments.filter(status=CourseEnrollment.Status.APPROVED).values_list(
            "student_id", flat=True
        )
    )
    selected_ids &= allowed_ids

    students_by_id = {
        enrollment.student_id: enrollment.student
        for enrollment in course.enrollments.filter(
            status=CourseEnrollment.Status.APPROVED,
            student_id__in=selected_ids,
        ).select_related("student")
    }
    for student in students_by_id.values():
        _copy_certificate_fields(certificate, student)

    StudentCertificate.objects.filter(template=certificate).exclude(
        student_id__in=selected_ids
    ).delete()
    messages.success(request, "Выдача сертификата обновлена.")
    return redirect("lessons:teacher_course_edit", course_id=course.pk)


@teacher_required
@require_POST
def teacher_enrollment_decide(request, course_id, enrollment_id, decision):
    course = _get_teacher_course(request.user, course_id)
    enrollment = get_object_or_404(
        CourseEnrollment,
        pk=enrollment_id,
        course=course,
        status=CourseEnrollment.Status.PENDING,
    )
    if decision == "approve":
        enrollment.status = CourseEnrollment.Status.APPROVED
        messages.success(request, "Заявка одобрена.")
    elif decision == "reject":
        enrollment.status = CourseEnrollment.Status.REJECTED
        messages.success(request, "Заявка отклонена.")
    else:
        get_object_or_404(CourseEnrollment.objects.none())
    enrollment.save(update_fields=["status", "updated_at"])
    return redirect("lessons:teacher_course_edit", course_id=course.pk)


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


def _format_hours(seconds):
    if not seconds:
        return "0 ч"
    hours = seconds / 3600
    if hours < 1:
        return f"{round(seconds / 60)} мин"
    return f"{hours:.1f} ч"

def _approved_enrollments(course):
    return (
        course.enrollments.filter(status=CourseEnrollment.Status.APPROVED)
        .select_related("student", "group")
        .order_by("student__last_name", "student__first_name", "student__username")
    )

def _student_display_name(student):
    full_name = f"{student.first_name} {student.last_name}".strip()
    return full_name or student.username or student.email

def _course_student_rows(course, group_id=None):
    enrollments = _approved_enrollments(course)
    if group_id:
        enrollments = enrollments.filter(group_id=group_id)

    lessons = list(course.lessons.all())
    lesson_ids = [lesson.pk for lesson in lessons]
    students = [enrollment.student for enrollment in enrollments]
    student_ids = [student.pk for student in students]

    progress_map = {
        (progress.student_id, progress.lesson_id): progress
        for progress in LessonProgress.objects.filter(
            student_id__in=student_ids,
            lesson_id__in=lesson_ids,
        )
    }

    time_by_student = {
        row["student_id"]: row["total_seconds"] or 0
        for row in LessonStudyTime.objects.filter(
            student_id__in=student_ids,
            lesson_id__in=lesson_ids,
        )
        .values("student_id")
        .annotate(total_seconds=Sum("seconds"))
    }

    rows = []
    for enrollment in enrollments:
        student = enrollment.student
        completed_count = sum(
            1 for lesson in lessons if (student.pk, lesson.pk) in progress_map
        )
        progress_percent = (
            round(completed_count * 100 / len(lessons)) if lessons else 0
        )
        last_progress = (
            LessonProgress.objects.filter(
                student=student,
                lesson__course=course,
            )
            .order_by("-completed_at")
            .first()
        )

        rows.append(
            {
                "enrollment": enrollment,
                "student": student,
                "name": _student_display_name(student),
                "completed_count": completed_count,
                "lessons_count": len(lessons),
                "progress_percent": progress_percent,
                "is_completed": lessons and completed_count == len(lessons),
                "time_label": _format_hours(time_by_student.get(student.pk, 0)),
                "last_activity": last_progress.completed_at if last_progress else None,
            }
        )
    return rows

def _course_progress_table(course, group_id=None):
    enrollments = _approved_enrollments(course)
    if group_id:
        enrollments = enrollments.filter(group_id=group_id)

    lessons = list(course.lessons.all())
    students = [enrollment.student for enrollment in enrollments]
    student_ids = [student.pk for student in students]
    lesson_ids = [lesson.pk for lesson in lessons]

    progress_map = {
        (progress.student_id, progress.lesson_id): progress
        for progress in LessonProgress.objects.filter(
            student_id__in=student_ids,
            lesson_id__in=lesson_ids,
        )
    }

    time_map = {
        (item.student_id, item.lesson_id): item.seconds
        for item in LessonStudyTime.objects.filter(
            student_id__in=student_ids,
            lesson_id__in=lesson_ids,
        )
    }

    lesson_has_tests = {}
    for lesson in lessons:
        lesson_has_tests[lesson.pk] = lesson.blocks.instance_of(
            TextQuestion,
            ChoiceQuestion,
        ).exists()

    rows = []
    for enrollment in enrollments:
        student = enrollment.student
        completed_count = 0
        total_seconds = 0
        lesson_cells = []

        for lesson in lessons:
            progress = progress_map.get((student.pk, lesson.pk))
            seconds = time_map.get((student.pk, lesson.pk), 0)
            total_seconds += seconds

            if progress:
                completed_count += 1

            lesson_cells.append(
                {
                    "lesson": lesson,
                    "is_completed": progress is not None,
                    "completed_at": progress.completed_at if progress else None,
                    "score_percent": (
                        progress.score_percent
                        if progress and lesson_has_tests.get(lesson.pk)
                        else None
                    ),
                    "time_label": _format_hours(seconds),
                }
            )

        progress_percent = (
            round(completed_count * 100 / len(lessons)) if lessons else 0
        )

        rows.append(
            {
                "enrollment": enrollment,
                "student": student,
                "name": _student_display_name(student),
                "lesson_cells": lesson_cells,
                "completed_count": completed_count,
                "lessons_count": len(lessons),
                "progress_percent": progress_percent,
                "time_label": _format_hours(total_seconds),
            }
        )

    return {
        "lessons": lessons,
        "rows": rows,
    }

def _teacher_courses_dashboard(user):
    courses = (
        Course.objects.filter(author=user)
        .select_related("category")
        .prefetch_related("lessons", "enrollments")
        .order_by("-created_at")
    )

    cards = []
    total_students = 0
    progress_values = []

    for course in courses:
        lessons_count = course.lessons.count()
        approved_count = course.enrollments.filter(
            status=CourseEnrollment.Status.APPROVED
        ).count()
        total_students += approved_count

        if lessons_count and approved_count:
            completed = LessonProgress.objects.filter(
                lesson__course=course,
                student__course_enrollments__course=course,
                student__course_enrollments__status=CourseEnrollment.Status.APPROVED,
            ).count()
            average_progress = round(completed * 100 / (approved_count * lessons_count))
        else:
            average_progress = 0

        if approved_count:
            progress_values.append(average_progress)

        total_seconds = (
            LessonStudyTime.objects.filter(lesson__course=course).aggregate(
                total=Sum("seconds")
            )["total"]
            or 0
        )

        cards.append(
            {
                "course": course,
                "students_count": approved_count,
                "lessons_count": lessons_count,
                "average_progress": average_progress,
                "duration_label": _format_hours(total_seconds),
            }
        )

    return {
        "course_cards": cards,
        "total_courses": courses.count(),
        "total_students": total_students,
        "average_progress": (
            round(sum(progress_values) / len(progress_values))
            if progress_values
            else 0
        ),
    }


@teacher_required
@require_POST
def teacher_group_create(request, course_id):
    course = _get_teacher_course(request.user, course_id)
    name = request.POST.get("name", "").strip()
    student_ids = request.POST.getlist("students")

    if not name:
        messages.error(request, "Введите название группы.")
        return redirect(f"{reverse('lessons:teacher_course_list')}?groups={course.pk}")

    group, created = StudentGroup.objects.get_or_create(course=course, name=name)
    if not created:
        messages.error(request, "Группа с таким названием уже существует.")
        return redirect(f"{reverse('lessons:teacher_course_list')}?groups={course.pk}")

    course.enrollments.filter(
        status=CourseEnrollment.Status.APPROVED,
        student_id__in=student_ids,
        group__isnull=True,
    ).update(group=group)

    messages.success(request, "Группа создана.")
    return redirect(f"{reverse('lessons:teacher_course_list')}?groups={course.pk}")

@teacher_required
@require_POST
def teacher_group_update(request, course_id, group_id):
    course = _get_teacher_course(request.user, course_id)
    group = get_object_or_404(StudentGroup, pk=group_id, course=course)

    name = request.POST.get("name", "").strip()
    selected_ids = {
        int(value) for value in request.POST.getlist("students") if value.isdigit()
    }

    if name:
        duplicate = StudentGroup.objects.filter(course=course, name=name).exclude(
            pk=group.pk
        )
        if duplicate.exists():
            messages.error(request, "Группа с таким названием уже существует.")
            return redirect(f"{reverse('lessons:teacher_course_list')}?groups={course.pk}")
        group.name = name
        group.save(update_fields=["name"])

    course.enrollments.filter(group=group).exclude(
        student_id__in=selected_ids
    ).update(group=None)

    course.enrollments.filter(
        status=CourseEnrollment.Status.APPROVED,
        student_id__in=selected_ids,
    ).update(group=group)

    messages.success(request, "Группа обновлена.")
    return redirect(f"{reverse('lessons:teacher_course_list')}?groups={course.pk}")

@teacher_required
@require_POST
def teacher_group_delete(request, course_id, group_id):
    course = _get_teacher_course(request.user, course_id)
    group = get_object_or_404(StudentGroup, pk=group_id, course=course)

    course.enrollments.filter(group=group).update(group=None)
    group.delete()

    messages.success(request, "Группа удалена. Студенты возвращены в общий список.")
    return redirect(f"{reverse('lessons:teacher_course_list')}?groups={course.pk}")