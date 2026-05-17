import os

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class FileSizeValidator:
    def __init__(self, max_size_mb: int):
        self.max_size_mb = max_size_mb
        self.max_bytes = max_size_mb * 1024 * 1024

    def __call__(self, file_obj):
        size = getattr(file_obj, "size", None)
        if size is None:
            return
        if size > self.max_bytes:
            raise ValidationError(
                f"Файл слишком большой: максимум {self.max_size_mb} МБ."
            )


@deconstructible
class UploadExtensionValidator:
    def __init__(self, allowed_extensions: set[str]):
        self.allowed_extensions = {
            ext.lower().lstrip(".") for ext in allowed_extensions
        }

    def __call__(self, file_obj):
        name = getattr(file_obj, "name", "")
        ext = os.path.splitext(name)[1].lower().lstrip(".")
        if ext and ext not in self.allowed_extensions:
            allowed_str = ", ".join(sorted(self.allowed_extensions))
            raise ValidationError(
                f"Недопустимый тип файла '.{ext}'. Разрешены: {allowed_str}."
            )
