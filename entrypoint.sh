#!/bin/bash

# Ждем, пока база данных будет готова
echo "Waiting for PostgreSQL..."
while ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER
do
  sleep 1
done
echo "PostgreSQL started"

# Запуск команды, переданной в docker-compose
exec "$@"