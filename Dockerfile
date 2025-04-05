FROM python:3.11-slim

# Установка рабочей директории
WORKDIR /app

# Установка необходимых зависимостей для системы
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libmagic1 \
    netcat-traditional \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Установка зависимостей Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Копирование проекта
COPY . /app/

# Создание директорий, если они не существуют
RUN mkdir -p /app/static /app/media/products /app/media/users/photos /app/media/chat_files /app/logs

# Установка прав на entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Открытие порта для Django
EXPOSE 8000

# Запуск entrypoint скрипта
ENTRYPOINT ["/app/entrypoint.sh"]