from apps.lessons.models import Block, BlockType, Course, Lesson
from django.contrib import admin

admin.site.register(Block)
admin.site.register(BlockType)


class BlockInline(admin.TabularInline):
    model = Block
    extra = 1


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    inlines = [BlockInline]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    inlines = [LessonInline]
