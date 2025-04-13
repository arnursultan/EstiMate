from django.http import FileResponse
import mimetypes
import os
from django.conf import settings


class BetterFileResponse(FileResponse):
    """
    Расширенный FileResponse с улучшенным определением Content-Type
    и дополнительными заголовками для мобильных клиентов
    """

    def __init__(self, *args, filename=None, **kwargs):
        super().__init__(*args, **kwargs)

        if filename:
            # Получаем расширение файла
            ext = filename.split('.')[-1].lower() if '.' in filename else ''

            # Используем словарь MIME-типов из настроек
            content_type = None
            if hasattr(settings, 'MIMETYPES') and ext in settings.MIMETYPES:
                content_type = settings.MIMETYPES[ext]
            else:
                # Резервный вариант - используем стандартный механизм
                content_type, encoding = mimetypes.guess_type(filename)

            if content_type:
                self['Content-Type'] = content_type

            # Устанавливаем имя файла
            name = os.path.basename(filename)
            self['Content-Disposition'] = f'inline; filename="{name}"'

            # Разрешаем кэширование
            self['Cache-Control'] = 'max-age=86400'  # Кэширование на 1 день

            # Разрешаем Range запросы для видео файлов
            if content_type and content_type.startswith('video/'):
                self['Accept-Ranges'] = 'bytes'