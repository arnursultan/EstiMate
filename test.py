import asyncio
import websockets
import json


async def test_websocket():
    # Подставьте ID чата, который существует в вашей базе данных
    chat_id = 1  # ID существующего чата

    # Подставьте ваш JWT токен доступа (access token)
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzQzODQ1OTQ5LCJpYXQiOjE3NDM3NTk1NDksImp0aSI6IjllMzhiODg4YzcyODQxNGZiOGIyOGQ5OWZkYmNkOTBiIiwidXNlcl9pZCI6MTN9.9quI9zuwUjXrMsDBG6aJ7w2In_giqfo46wHP8S9j8XE"  # Ваш реальный JWT токен

    # Создаем полный URI для подключения к WebSocket
    uri = f"ws://localhost:8000/ws/chat/{chat_id}/?token={token}"

    print(f"Подключение к {uri}")

    try:
        async with websockets.connect(uri) as websocket:
            print("Соединение установлено")

            # Отправляем первое сообщение
            message = {
                "type": "text",
                "message": "Тестовое сообщение из Python-скрипта"
            }
            await websocket.send(json.dumps(message))
            print(f"Отправлено: {message}")

            # Получаем ответ
            response = await websocket.recv()
            print(f"Получено: {response}")

            # Ждем 5 секунд и отправляем еще одно сообщение
            await asyncio.sleep(5)

            message = {
                "type": "text",
                "message": "Еще одно тестовое сообщение"
            }
            await websocket.send(json.dumps(message))
            print(f"Отправлено: {message}")

            # Получаем ответ
            response = await websocket.recv()
            print(f"Получено: {response}")

    except Exception as e:
        print(f"Ошибка: {str(e)}")


asyncio.run(test_websocket())