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


def _parse_int_set(raw: str) -> set[int]:
    if not raw:
        return set()
    parts = [p.strip() for p in raw.split(',')]
    out: set[int] = set()
    for p in parts:
        if not p:
            continue
        try:
            out.add(int(p))
        except ValueError:
            continue
    return out

# Админы бота (кто может загружать голосовые памятки).
# Формат: "123,456".
# Если переменная не задана — по умолчанию ваш id.
ADMIN_USER_IDS = _parse_int_set(os.getenv('ADMIN_USER_IDS', '459695859'))
