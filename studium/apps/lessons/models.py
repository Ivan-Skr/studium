from django.db import models


class Course(models.Model):
    name = models.CharField("Название", max_length=30)
    description = models.CharField("Описание", max_length=250)
    image = models.ImageField("Изображение", upload_to="images/")
    is_published = models.BooleanField("Опубликован", default=True)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)

    class Meta:
        verbose_name = "Course"
        verbose_name_plural = "Courses"

    def __str__(self):
        return self.name


class Lesson(models.Model):
    name = models.CharField("Название", max_length=50)
    course = models.ForeignKey("lessons.Course", on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Lessons"
        verbose_name_plural = "Lessons"

    def __str__(self):
        return self.name


class Block(models.Model):
    type = models.ForeignKey("lessons.BlockType", on_delete=models.CASCADE)
    lesson = models.ForeignKey("lessons.Lesson", on_delete=models.CASCADE)
    text = models.TextField("Текст", blank=True)
    image = models.ImageField("Изображение", upload_to="images/", blank=True)
    # video
    # audio
    # test

    class Meta:
        verbose_name = "Block"
        verbose_name_plural = "Blocks"

    def __str__(self):
        return self.type


class BlockType(models.Model):
    name = models.CharField("Название", max_length=50)

    class Meta:
        verbose_name = "BlockType"
        verbose_name_plural = "BlockTypes"

    def __str__(self):
        return self.name
