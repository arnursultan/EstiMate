FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt и устанавливаем зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем entrypoint скрипт и делаем его исполняемым
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Копируем проект
COPY . .

# Создаем директории для статических и медиа файлов
RUN mkdir -p /app/static /app/media

# Открываем порт для Django
EXPOSE 8000

# Запускаем entrypoint скрипт
ENTRYPOINT ["/app/entrypoint.sh"]