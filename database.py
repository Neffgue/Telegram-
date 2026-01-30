"""
Модуль для работы с базой данных
"""
import sqlite3
from datetime import datetime

DATABASE_NAME = 'pillow_bot.db'

def init_database():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Создаем таблицу для хранения времени напоминаний
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            reminder_time TEXT NOT NULL,
            timezone TEXT NOT NULL DEFAULT 'Europe/Moscow',
            created_at TEXT NOT NULL
        )
    ''')

    # Миграция: добавляем колонку timezone если её нет (для существующих баз данных)
    try:
        cursor.execute('SELECT timezone FROM reminders LIMIT 1')
    except sqlite3.OperationalError:
        try:
            cursor.execute('ALTER TABLE reminders ADD COLUMN timezone TEXT DEFAULT \'Europe/Moscow\'')
            cursor.execute('UPDATE reminders SET timezone = \'Europe/Moscow\' WHERE timezone IS NULL')
        except sqlite3.OperationalError:
            pass

    # Миграция: добавляем колонку username если её нет
    try:
        cursor.execute('SELECT username FROM reminders LIMIT 1')
    except sqlite3.OperationalError:
        try:
            cursor.execute('ALTER TABLE reminders ADD COLUMN username TEXT')
        except sqlite3.OperationalError:
            pass

    # Создаем таблицу для отслеживания принятых таблеток (по датам)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pills_taken (
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            taken_at TEXT NOT NULL,
            PRIMARY KEY (user_id, date)
        )
    ''')

    # Создаем таблицу для логирования всех взаимодействий с ботом
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            interaction_type TEXT NOT NULL,
            interaction_data TEXT,
            timestamp TEXT NOT NULL
        )
    ''')

    # Голосовые памятки (общий пул)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voice_memos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # Выдача памяток пользователям (чтобы каждому отдавать каждую памятку один раз)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voice_deliveries (
            user_id INTEGER NOT NULL,
            memo_id INTEGER NOT NULL,
            delivered_at TEXT NOT NULL,
            PRIMARY KEY (user_id, memo_id),
            FOREIGN KEY (memo_id) REFERENCES voice_memos (id)
        )
    ''')

    # Лимит 1 памяточка в день (кроме админа) — отмечаем факт выдачи на дату
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voice_memo_daily (
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            taken_at TEXT NOT NULL,
            PRIMARY KEY (user_id, date)
        )
    ''')

    conn.commit()
    conn.close()


def set_reminder_time(user_id: int, time: str, timezone: str = 'Europe/Moscow', username: str = None):
    """Устанавливает время напоминания для пользователя"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Если username не передан, пытаемся получить существующий
    if username is None:
        cursor.execute('SELECT username FROM reminders WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        username = result[0] if result else None

    cursor.execute('''
        INSERT OR REPLACE INTO reminders (user_id, username, reminder_time, timezone, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, time, timezone, datetime.now().isoformat()))

    conn.commit()
    conn.close()


def set_user_timezone(user_id: int, timezone: str, username: str = None):
    """Устанавливает часовой пояс для пользователя"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Обновляем часовой пояс, сохраняя существующее время напоминания
    cursor.execute('SELECT reminder_time, username FROM reminders WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    reminder_time = result[0] if result else '09:00'
    if username is None and result:
        username = result[1]

    cursor.execute('''
        INSERT OR REPLACE INTO reminders (user_id, username, reminder_time, timezone, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, reminder_time, timezone, datetime.now().isoformat()))

    conn.commit()
    conn.close()


def get_user_timezone(user_id: int) -> str:
    """Получает часовой пояс пользователя"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT timezone FROM reminders WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    conn.close()

    return result[0] if result else 'Europe/Moscow'


def get_reminder_time(user_id: int) -> str:
    """Получает время напоминания для пользователя"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT reminder_time FROM reminders WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    conn.close()

    return result[0] if result else None


def get_all_users_with_reminders():
    """Получает всех пользователей с установленными напоминаниями"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT user_id, reminder_time, timezone FROM reminders')
    results = cursor.fetchall()

    conn.close()

    return results


def mark_pill_taken(user_id: int, date: str):
    """Отмечает, что пользователь выпил таблеточку в указанную дату"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO pills_taken (user_id, date, taken_at)
        VALUES (?, ?, ?)
    ''', (user_id, date, datetime.now().isoformat()))

    conn.commit()
    conn.close()


def is_pill_taken_today(user_id: int) -> bool:
    """Проверяет, выпил ли пользователь таблеточку сегодня"""
    from datetime import date
    today = date.today().isoformat()

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT 1 FROM pills_taken
        WHERE user_id = ? AND date = ?
    ''', (user_id, today))

    result = cursor.fetchone()
    conn.close()

    return result is not None


def clear_pill_taken_today(user_id: int):
    """Очищает отметку о выпитой таблеточке на сегодня"""
    from datetime import date
    today = date.today().isoformat()

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        DELETE FROM pills_taken
        WHERE user_id = ? AND date = ?
    ''', (user_id, today))

    conn.commit()
    conn.close()


def get_days_count(user_id: int) -> int:
    """Получает количество дней использования бота (количество записей о выпитых таблеточках)"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT COUNT(DISTINCT date) FROM pills_taken
        WHERE user_id = ?
    ''', (user_id,))

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else 0


def get_first_use_date(user_id: int) -> str:
    """Получает дату первого использования бота"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT MIN(date) FROM pills_taken
        WHERE user_id = ?
    ''', (user_id,))

    result = cursor.fetchone()
    conn.close()

    return result[0] if result and result[0] else None


def log_interaction(user_id: int, interaction_type: str, interaction_data: str = None, username: str = None):
    """Логирует взаимодействие пользователя с ботом"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO bot_interactions (user_id, username, interaction_type, interaction_data, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, interaction_type, interaction_data, datetime.now().isoformat()))

    conn.commit()
    conn.close()


# --- Голосовые памятки ---

def add_voice_memo(file_id: str) -> int:
    """Сохраняет голосовую памятку (file_id Telegram). Возвращает id записи."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO voice_memos (file_id, created_at)
        VALUES (?, ?)
    ''', (file_id, datetime.now().isoformat()))

    memo_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return memo_id


def get_next_voice_memo_for_user(user_id: int):
    """Берет следующую (самую раннюю) памятку, которую пользователь еще не получал."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT vm.id, vm.file_id, vm.created_at
        FROM voice_memos vm
        LEFT JOIN voice_deliveries vd
               ON vd.memo_id = vm.id AND vd.user_id = ?
        WHERE vd.memo_id IS NULL
        ORDER BY vm.id ASC
        LIMIT 1
    ''', (user_id,))

    row = cursor.fetchone()
    conn.close()
    return row


def mark_voice_memo_delivered(user_id: int, memo_id: int):
    """Отмечает, что памятка выдана пользователю (один раз)."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR IGNORE INTO voice_deliveries (user_id, memo_id, delivered_at)
        VALUES (?, ?, ?)
    ''', (user_id, memo_id, datetime.now().isoformat()))

    conn.commit()
    conn.close()


def is_voice_memo_taken_today(user_id: int) -> bool:
    """Проверяет, получал ли пользователь памяточку сегодня (для лимита 1/день)."""
    from datetime import date
    today = date.today().isoformat()

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT 1 FROM voice_memo_daily
        WHERE user_id = ? AND date = ?
    ''', (user_id, today))

    result = cursor.fetchone()
    conn.close()

    return result is not None


def mark_voice_memo_taken_today(user_id: int):
    """Отмечает, что пользователь получил памяточку сегодня (для лимита 1/день)."""
    from datetime import date
    today = date.today().isoformat()

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO voice_memo_daily (user_id, date, taken_at)
        VALUES (?, ?, ?)
    ''', (user_id, today, datetime.now().isoformat()))

    conn.commit()
    conn.close()


def list_voice_memos(limit: int = 10):
    """Список последних добавленных памяток (новые сверху)."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute(
        'SELECT id, file_id, created_at FROM voice_memos ORDER BY id DESC LIMIT ?',
        (int(limit),)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def delete_voice_memo(memo_id: int) -> bool:
    """Удаляет памятку и все её выдачи пользователям. Возвращает True если была удалена."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT 1 FROM voice_memos WHERE id = ?', (memo_id,))
    exists = cursor.fetchone() is not None
    if not exists:
        conn.close()
        return False

    cursor.execute('DELETE FROM voice_deliveries WHERE memo_id = ?', (memo_id,))
    cursor.execute('DELETE FROM voice_memos WHERE id = ?', (memo_id,))

    conn.commit()
    conn.close()
    return True
