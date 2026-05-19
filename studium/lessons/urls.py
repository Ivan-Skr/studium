from django.urls import path

from . import teaching_views, views

app_name = "lessons"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("teaching/", teaching_views.teacher_course_list, name="teacher_course_list"),
    path(
        "teaching/new/",
        teaching_views.teacher_course_create,
        name="teacher_course_create",
    ),
    path(
        "teaching/<int:course_id>/edit/",
        teaching_views.teacher_course_edit,
        name="teacher_course_edit",
    ),
    path(
        "teaching/<int:course_id>/delete/",
        teaching_views.teacher_course_delete,
        name="teacher_course_delete",
    ),
    path(
        "teaching/<int:course_id>/lessons/add/",
        teaching_views.teacher_lesson_create,
        name="teacher_lesson_create",
    ),
    path(
        "teaching/<int:course_id>/lessons/<int:lesson_id>/",
        teaching_views.teacher_lesson_editor,
        name="teacher_lesson_editor",
    ),
    path(
        "teaching/<int:course_id>/lessons/<int:lesson_id>/edit/",
        teaching_views.teacher_lesson_edit,
        name="teacher_lesson_edit",
    ),
    path(
        "teaching/<int:course_id>/lessons/<int:lesson_id>/blocks/add/<slug:block_type>/",
        teaching_views.teacher_block_create,
        name="teacher_block_create",
    ),
    path(
        "teaching/<int:course_id>/lessons/<int:lesson_id>/blocks/<int:block_id>/edit/",
        teaching_views.teacher_block_edit,
        name="teacher_block_edit",
    ),
    path(
        "teaching/<int:course_id>/lessons/<int:lesson_id>/blocks/<int:block_id>/delete/",
        teaching_views.teacher_block_delete,
        name="teacher_block_delete",
    ),
    path(
        "teaching/<int:course_id>/lessons/<int:lesson_id>/blocks/<int:block_id>/move/<slug:direction>/",
        teaching_views.teacher_block_move,
        name="teacher_block_move",
    ),
    path(
        "teaching/<int:course_id>/lessons/<int:lesson_id>/move/<slug:direction>/",
        teaching_views.teacher_lesson_move,
        name="teacher_lesson_move",
    ),
    path(
        "teaching/<int:course_id>/lessons/<int:lesson_id>/delete/",
        teaching_views.teacher_lesson_delete,
        name="teacher_lesson_delete",
    ),
    path("courses/<int:course_id>/", views.course_detail, name="course_detail"),
    path(
        "courses/<int:course_id>/lessons/<int:lesson_id>/",
        views.lesson_detail,
        name="lesson_detail",
    ),
    path(
        "courses/<int:course_id>/lessons/<int:lesson_id>/blocks/<int:block_id>/text/",
        views.submit_text_answer,
        name="submit_text_answer",
    ),
    path(
        "courses/<int:course_id>/lessons/<int:lesson_id>/blocks/<int:block_id>/choice/",
        views.submit_choice_answer,
        name="submit_choice_answer",
    ),
    path(
        "courses/<int:course_id>/lessons/<int:lesson_id>/blocks/<int:block_id>/file/",
        views.submit_file_answer,
        name="submit_file_answer",
    ),
]
