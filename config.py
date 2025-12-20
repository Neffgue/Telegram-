"""
Конфигурационный файл для Telegram бота
"""
import os

# Пытаемся загрузить переменные окружения из .env файла (если он есть)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Токен бота от @BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# ID пользователя (опционально, можно оставить пустым если бот открыт для всех)
ALLOWED_USER_ID = os.getenv('ALLOWED_USER_ID', '')

