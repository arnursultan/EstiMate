#!/bin/sh

set -e

# Ожидание доступности PostgreSQL
echo "Waiting for PostgreSQL..."
while ! nc -z ${POSTGRES_HOST:-db} ${POSTGRES_PORT:-5432}; do
  sleep 0.1
done
echo "PostgreSQL is up!"

# Ожидание доступности Redis
echo "Waiting for Redis..."
while ! nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
  sleep 0.1
done
echo "Redis is up!"

# Создание директорий для логов, если они не существуют
mkdir -p /app/logs

# Устанавливаем правильные разрешения для логов
touch /app/logs/chat.log /app/logs/errors.log /app/logs/store_payments.log
chmod 666 /app/logs/chat.log /app/logs/errors.log /app/logs/store_payments.log

# Применяем миграции базы данных
echo "Applying database migrations..."
python manage.py migrate

# Собираем статические файлы
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Запускаем команду из docker-compose
echo "Starting the application..."
exec "$@"