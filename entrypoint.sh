#!/bin/bash

set -e

# Если это запуск celery — не выполнять миграции
if [[ "$1" == "celery" ]]; then
  echo "Starting Celery worker..."
  exec "$@"
fi

# Встроенная проверка соединения с PostgreSQL
echo "Testing database connection..."
python -c "
import sys
import psycopg2
import os
import time

# Пытаемся подключиться к базе данных
for i in range(30):
    try:
        conn = psycopg2.connect(
            dbname=os.environ.get('DB_NAME', 'baza1_db'),
            user=os.environ.get('DB_USER', 'baza1'),
            password=os.environ.get('DB_PASSWORD', '12345678'),
            host=os.environ.get('DB_HOST', 'db'),
            port=os.environ.get('DB_PORT', '5432')
        )
        conn.close()
        print('Database connection successful!')
        break
    except psycopg2.OperationalError as e:
        print(f'Waiting for database... ({i+1}/30) Error: {e}')
        time.sleep(1)
else:
    print('Could not connect to the database after 30 seconds.')
    sys.exit(1)
"

echo "Applying database migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting the application..."
exec "$@"
