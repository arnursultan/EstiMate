FROM python:3.11-slim

# Установка рабочей директории
WORKDIR /app

# Установка необходимых зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Установка зависимостей Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Копирование проекта
COPY . /app/

# Создание директорий для логов
RUN mkdir -p /app/logs /app/media /app/static

# Установка прав на entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Открытие порта
EXPOSE 8000

# Запуск entrypoint скрипта
ENTRYPOINT ["/app/entrypoint.sh"]