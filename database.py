"""
Модуль для работы с базой данных
"""
import sqlite3
import os
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

def get_all_interactions():
    """Получает все взаимодействия пользователей с ботом"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT bi.id, bi.user_id, bi.username, bi.interaction_type, bi.interaction_data, bi.timestamp,
               r.reminder_time, r.timezone
        FROM bot_interactions bi
        LEFT JOIN reminders r ON bi.user_id = r.user_id
        ORDER BY bi.timestamp DESC
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return results

def get_user_interactions(user_id: int):
    """Получает все взаимодействия конкретного пользователя"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT bi.id, bi.user_id, bi.username, bi.interaction_type, bi.interaction_data, bi.timestamp,
               r.reminder_time, r.timezone
        FROM bot_interactions bi
        LEFT JOIN reminders r ON bi.user_id = r.user_id
        WHERE bi.user_id = ?
        ORDER BY bi.timestamp DESC
    ''', (user_id,))
    
    results = cursor.fetchall()
    conn.close()
    
    return results

def get_all_users_data():
    """Получает данные всех пользователей с их напоминаниями и историей"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            r.user_id,
            r.username,
            r.reminder_time,
            r.timezone,
            r.created_at,
            (SELECT COUNT(*) FROM pills_taken WHERE user_id = r.user_id) as pills_count,
            (SELECT MIN(date) FROM pills_taken WHERE user_id = r.user_id) as first_pill_date,
            (SELECT COUNT(*) FROM bot_interactions WHERE user_id = r.user_id) as interactions_count
        FROM reminders r
        ORDER BY r.created_at DESC
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return results


