from .forms import (
    AudioBlockForm,
    ChoiceQuestionForm,
    FileQuestionForm,
    ImageBlockForm,
    TeacherFileBlockForm,
    TextBlockForm,
    TextQuestionForm,
    VideoBlockForm,
)
from .models import (
    AudioBlock,
    ChoiceQuestion,
    FileQuestion,
    ImageBlock,
    TeacherFileBlock,
    TextBlock,
    TextQuestion,
    VideoBlock,
)

BLOCK_TYPES = {
    "text": {
        "label": "Текст",
        "description": "Текстовый материал",
        "model": TextBlock,
        "form": TextBlockForm,
    },
    "image": {
        "label": "Изображение",
        "description": "Фото или иллюстрация",
        "model": ImageBlock,
        "form": ImageBlockForm,
    },
    "video": {
        "label": "Видео",
        "description": "Видеофайл",
        "model": VideoBlock,
        "form": VideoBlockForm,
    },
    "audio": {
        "label": "Аудио",
        "description": "Аудиозапись",
        "model": AudioBlock,
        "form": AudioBlockForm,
    },
    "teacher_file": {
        "label": "Файл",
        "description": "Материал для скачивания",
        "model": TeacherFileBlock,
        "form": TeacherFileBlockForm,
    },
    "text_question": {
        "label": "Текстовый вопрос",
        "description": "Ответ в свободной форме",
        "model": TextQuestion,
        "form": TextQuestionForm,
    },
    "choice_question": {
        "label": "Вопрос с выбором",
        "description": "Один или несколько вариантов",
        "model": ChoiceQuestion,
        "form": ChoiceQuestionForm,
    },
    "file_question": {
        "label": "Задание с файлом",
        "description": "Студент загружает файл",
        "model": FileQuestion,
        "form": FileQuestionForm,
    },
}


def get_block_type_slug(block):
    for slug, config in BLOCK_TYPES.items():
        if isinstance(block, config["model"]):
            return slug
    return None


def get_block_type_label(block):
    slug = get_block_type_slug(block)
    if slug:
        return BLOCK_TYPES[slug]["label"]
    return "Блок"
