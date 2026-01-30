"""
Telegram бот для ежедневных напоминаний о таблеточках
"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)
from datetime import time as dt_time, datetime, timedelta
import pytz

import config
import database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Отключаем лишние логи от APScheduler (если используется)
logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)

# Состояния для ConversationHandler
SELECTING_TIME, CONFIRMING_TIME = range(2)

MEMO_BUTTON_TEXT = "🎧 Получить памятку"

# Создаем постоянную клавиатуру с кнопками меню
def get_main_keyboard():
    """Возвращает постоянную клавиатуру с кнопками меню"""
    keyboard = [
        [KeyboardButton("⏰ Изменить время"), KeyboardButton("⚙️ Настройки")],
        [KeyboardButton("ℹ️ Информация"), KeyboardButton("🏠 Главное меню")],
        [KeyboardButton(MEMO_BUTTON_TEXT)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    logger.info(f"Start command received from user {update.effective_user.id}")
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    database.log_interaction(user_id, "start_command", None, username)
    
    welcome_message = (
        "💊 Привет, малыш! 👋\n\n"
        "Я сделал тебе бота, который будет напоминать, "
        "чтоб ты выпила таблеточку и чувствовала себя хорошо. 💕\n\n"
        "Выбери время, когда тебе удобно получать напоминания: ⏰"
    )
    
    # Создаем клавиатуру с кнопками выбора времени
    keyboard = []
    times = [
        ("08:00", "🌅 Утро (8:00)"),
        ("09:00", "🌞 Утро (9:00)"),
        ("10:00", "☀️ Утро (10:00)"),
        ("12:00", "🌤️ Обед (12:00)"),
        ("13:00", "🍽️ Обед (13:00)"),
        ("14:00", "☕ День (14:00)"),
        ("18:00", "🌆 Вечер (18:00)"),
        ("19:00", "🌇 Вечер (19:00)"),
        ("20:00", "🌃 Вечер (20:00)"),
        ("21:00", "🌙 Вечер (21:00)"),
        ("Другое", "⏰ Выбрать другое время")
    ]
    
    # Разбиваем кнопки на ряды по 2
    for i in range(0, len(times), 2):
        row = []
        row.append(InlineKeyboardButton(times[i][1], callback_data=f"time_{times[i][0]}"))
        if i + 1 < len(times):
            row.append(InlineKeyboardButton(times[i+1][1], callback_data=f"time_{times[i+1][0]}"))
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Добавляем кнопку "Настройки" в конец клавиатуры
    keyboard.append([InlineKeyboardButton("⚙️ Настройки", callback_data="settings")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        # Отправляем постоянную клавиатуру
        await update.message.reply_text(
            "Используй кнопки ниже для навигации:",
            reply_markup=get_main_keyboard()
        )
        logger.info(f"Start message sent successfully to user {user_id}")
    except Exception as e:
        logger.error(f"Error sending start message to user {user_id}: {e}", exc_info=True)
        # Пробуем отправить без parse_mode
        try:
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)
            await update.message.reply_text("Используй кнопки ниже для навигации:", reply_markup=get_main_keyboard())
        except Exception as e2:
            logger.error(f"Error sending start message (second attempt) to user {user_id}: {e2}", exc_info=True)
    
    return SELECTING_TIME

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "settings":
        # Логируем взаимодействие
        username = query.from_user.username or query.from_user.first_name
        database.log_interaction(query.from_user.id, "settings_opened", None, username)
        # Показываем меню настроек
        keyboard = [
            [InlineKeyboardButton("🧪 Тест", callback_data="test_notification")],
            [InlineKeyboardButton("🌍 Выбор города", callback_data="select_city")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚙️ Настройки:\n\n"
            "Выбери действие:",
            reply_markup=reply_markup
        )
        return SELECTING_TIME
    
    if data == "test_notification":
        # Логируем взаимодействие
        username = query.from_user.username or query.from_user.first_name
        database.log_interaction(query.from_user.id, "test_notification", None, username)
        # Отправляем тестовое уведомление
        reminder_message = (
            "💊 Выпей таблеточку, малыш. Люблю тебя, хорошего дня! 💕"
        )
        keyboard = [
            [InlineKeyboardButton("💖 Я уже выпила таблеточку, любимый", callback_data="pill_taken")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            reminder_message,
            reply_markup=reply_markup
        )
        return SELECTING_TIME
    
    if data == "select_city":
        # Показываем выбор города
        keyboard = [
            [InlineKeyboardButton("🏙️ Санкт-Петербург (UTC+3)", callback_data="city_spb")],
            [InlineKeyboardButton("🏔️ Уфа (UTC+5)", callback_data="city_ufa")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🌍 Выбери город для установки часового пояса:",
            reply_markup=reply_markup
        )
        return SELECTING_TIME
    
    if data == "city_spb":
        # Устанавливаем часовой пояс для Санкт-Петербурга (UTC+3, MSK)
        timezone = 'Europe/Moscow'
        city_name = "Санкт-Петербург (UTC+3)"
        username = query.from_user.username or query.from_user.first_name
        database.set_user_timezone(user_id, timezone, username)
        database.log_interaction(user_id, "timezone_changed", f"Санкт-Петербург (UTC+3)", username)
        
        # Перепланируем напоминание с новым часовым поясом
        reminder_time = database.get_reminder_time(user_id)
        if reminder_time:
            schedule_reminder(user_id, reminder_time, context.application.job_queue, timezone)
        
        await query.edit_message_text(
            f"✅ Часовой пояс изменен на {city_name} 🌍\n\n"
            f"Напоминания теперь будут приходить согласно этому часовому поясу. 💕"
        )
        return ConversationHandler.END
    
    if data == "city_ufa":
        # Устанавливаем часовой пояс для Уфы (UTC+5)
        timezone = 'Asia/Yekaterinburg'
        city_name = "Уфа (UTC+5)"
        username = query.from_user.username or query.from_user.first_name
        database.set_user_timezone(user_id, timezone, username)
        database.log_interaction(user_id, "timezone_changed", f"Уфа (UTC+5)", username)
        
        # Перепланируем напоминание с новым часовым поясом
        reminder_time = database.get_reminder_time(user_id)
        if reminder_time:
            schedule_reminder(user_id, reminder_time, context.application.job_queue, timezone)
        
        await query.edit_message_text(
            f"✅ Часовой пояс изменен на {city_name} 🌍\n\n"
            f"Напоминания теперь будут приходить согласно этому часовому поясу. 💕"
        )
        return ConversationHandler.END
    
    if data == "back_to_main" or data == "main_menu":
        # Возвращаемся к главному меню
        keyboard = []
        times = [
            ("08:00", "🌅 Утро (8:00)"),
            ("09:00", "🌞 Утро (9:00)"),
            ("10:00", "☀️ Утро (10:00)"),
            ("12:00", "🌤️ Обед (12:00)"),
            ("13:00", "🍽️ Обед (13:00)"),
            ("14:00", "☕ День (14:00)"),
            ("18:00", "🌆 Вечер (18:00)"),
            ("19:00", "🌇 Вечер (19:00)"),
            ("20:00", "🌃 Вечер (20:00)"),
            ("21:00", "🌙 Вечер (21:00)"),
            ("Другое", "⏰ Выбрать другое время")
        ]
        for i in range(0, len(times), 2):
            row = []
            row.append(InlineKeyboardButton(times[i][1], callback_data=f"time_{times[i][0]}"))
            if i + 1 < len(times):
                row.append(InlineKeyboardButton(times[i+1][1], callback_data=f"time_{times[i+1][0]}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("⚙️ Настройки", callback_data="settings")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "💊 Привет, малыш! 👋\n\n"
            "Я сделал тебе бота, который будет напоминать, "
            "чтоб ты выпила таблеточку и чувствовала себя хорошо. 💕\n\n"
            "Выбери время, когда тебе удобно получать напоминания: ⏰",
            reply_markup=reply_markup
        )
        return SELECTING_TIME
    
    if data == "change_time_btn":
        # Переход к выбору времени
        keyboard = []
        times = [
            ("08:00", "🌅 Утро (8:00)"),
            ("09:00", "🌞 Утро (9:00)"),
            ("10:00", "☀️ Утро (10:00)"),
            ("12:00", "🌤️ Обед (12:00)"),
            ("13:00", "🍽️ Обед (13:00)"),
            ("14:00", "☕ День (14:00)"),
            ("18:00", "🌆 Вечер (18:00)"),
            ("19:00", "🌇 Вечер (19:00)"),
            ("20:00", "🌃 Вечер (20:00)"),
            ("21:00", "🌙 Вечер (21:00)"),
            ("Другое", "⏰ Выбрать другое время")
        ]
        for i in range(0, len(times), 2):
            row = []
            row.append(InlineKeyboardButton(times[i][1], callback_data=f"time_{times[i][0]}"))
            if i + 1 < len(times):
                row.append(InlineKeyboardButton(times[i+1][1], callback_data=f"time_{times[i+1][0]}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("⚙️ Настройки", callback_data="settings")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⏰ Выбери новое время для напоминаний:",
            reply_markup=reply_markup
        )
        return SELECTING_TIME
    
    if data == "info_btn":
        # Логируем взаимодействие
        username = query.from_user.username or query.from_user.first_name
        database.log_interaction(query.from_user.id, "info_viewed", None, username)
        # Показываем информацию
        user_id = query.from_user.id
        days_count = database.get_days_count(user_id)
        first_date = database.get_first_use_date(user_id)
        reminder_time = database.get_reminder_time(user_id)
        
        info_message = (
            f"ℹ️ Информация о твоем использовании бота:\n\n"
            f"📊 Количество дней, когда ты пила таблеточку с помощью бота: {days_count} дней\n\n"
        )
        
        if first_date:
            from datetime import datetime
            try:
                first_dt = datetime.fromisoformat(first_date)
                days_since_first = (datetime.now().date() - first_dt.date()).days + 1
                info_message += f"📅 Первое использование: {first_dt.strftime('%d.%m.%Y')}\n"
                info_message += f"⏱️ Всего дней с ботом: {days_since_first} дней\n\n"
            except:
                pass
        
        if reminder_time:
            timezone = database.get_user_timezone(user_id)
            info_message += f"⏰ Время напоминания: {reminder_time}\n"
            info_message += f"🌍 Часовой пояс: {timezone}\n"
        else:
            info_message += "⏰ Время напоминания: не установлено\n"
        
        keyboard = [
            [InlineKeyboardButton("⏰ Изменить время", callback_data="change_time_btn")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(
                info_message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing message for info: {e}")
            # Если не удалось отредактировать, отправляем новое сообщение
            await query.message.reply_text(
                info_message,
                reply_markup=reply_markup
            )
        return SELECTING_TIME
    
    if data.startswith("time_"):
        time_str = data[5:]  # Убираем префикс "time_"
        
        if time_str == "Другое":
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "💭 Напиши время в формате ЧЧ:ММ (например, 15:30 или 09:15):",
                reply_markup=reply_markup
            )
            return CONFIRMING_TIME
        else:
            # Проверяем формат времени
            try:
                hour, minute = map(int, time_str.split(':'))
                if 0 <= hour < 24 and 0 <= minute < 60:
                    timezone = database.get_user_timezone(user_id)
                    username = query.from_user.username or query.from_user.first_name
                    # При смене времени очищаем отметку о выпитой таблеточке сегодня
                    database.clear_pill_taken_today(user_id)
                    database.set_reminder_time(user_id, time_str, timezone, username)
                    database.log_interaction(user_id, "reminder_time_changed", time_str, username)
                    logger.info(f"User {user_id} selected time {time_str} in timezone {timezone}")
                    schedule_reminder(user_id, time_str, context.application.job_queue, timezone)
                    
                    keyboard = [
                        [InlineKeyboardButton("⏰ Изменить время", callback_data="change_time_btn")],
                        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
                        [InlineKeyboardButton("ℹ️ Информация", callback_data="info_btn")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(
                        f"✅ Отлично, малыш! 💕\n\n"
                        f"Я буду напоминать тебе каждый день в {time_str} ⏰\n\n"
                        f"Не забудь выпить таблеточку! 💊",
                        reply_markup=reply_markup
                    )
                    # Возвращаем ConversationHandler.END, но кнопки будут работать через отдельный обработчик
                    return ConversationHandler.END
                else:
                    keyboard = [
                        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(
                        "❌ Время указано неверно. Попробуй еще раз:",
                        reply_markup=reply_markup
                    )
                    return CONFIRMING_TIME
            except ValueError:
                keyboard = [
                    [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "❌ Неверный формат времени. Напиши время в формате ЧЧ:ММ (например, 15:30):",
                    reply_markup=reply_markup
                )
                return CONFIRMING_TIME
    
    return SELECTING_TIME

async def handle_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик пользовательского времени"""
    user_id = update.effective_user.id
    time_str = update.message.text.strip()
    
    # Проверяем формат времени
    try:
        hour, minute = map(int, time_str.split(':'))
        if 0 <= hour < 24 and 0 <= minute < 60:
            time_formatted = f"{hour:02d}:{minute:02d}"
            timezone = database.get_user_timezone(user_id)
            # При смене времени очищаем отметку о выпитой таблеточке сегодня
            database.clear_pill_taken_today(user_id)
            username = update.effective_user.username or update.effective_user.first_name
            database.set_reminder_time(user_id, time_formatted, timezone, username)
            database.log_interaction(user_id, "reminder_time_changed", time_formatted, username)
            logger.info(f"User {user_id} entered custom time {time_formatted} in timezone {timezone}")
            schedule_reminder(user_id, time_formatted, context.application.job_queue, timezone)
            
            keyboard = [
                [InlineKeyboardButton("⏰ Изменить время", callback_data="change_time_btn")],
                [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
                [InlineKeyboardButton("ℹ️ Информация", callback_data="info_btn")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ Отлично, малыш! 💕\n\n"
                f"Я буду напоминать тебе каждый день в {time_formatted} ⏰\n\n"
                f"Не забудь выпить таблеточку! 💊",
                reply_markup=reply_markup
            )
            # Возвращаем ConversationHandler.END, но кнопки будут работать через отдельный обработчик
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "❌ Время указано неверно. Укажи часы от 0 до 23 и минуты от 0 до 59.\n"
                "Попробуй еще раз (формат ЧЧ:ММ):"
            )
            return CONFIRMING_TIME
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат времени. Напиши время в формате ЧЧ:ММ (например, 15:30):"
        )
        return CONFIRMING_TIME

async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Информация'"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    database.log_interaction(user_id, "info_viewed", None, username)
    
    days_count = database.get_days_count(user_id)
    first_date = database.get_first_use_date(user_id)
    reminder_time = database.get_reminder_time(user_id)
    
    info_message = (
        f"ℹ️ Информация о твоем использовании бота:\n\n"
        f"📊 Количество дней, когда ты пила таблеточку с помощью бота: {days_count} дней\n\n"
    )
    
    if first_date:
        from datetime import datetime
        try:
            first_dt = datetime.fromisoformat(first_date)
            days_since_first = (datetime.now().date() - first_dt.date()).days + 1
            info_message += f"📅 Первое использование: {first_dt.strftime('%d.%m.%Y')}\n"
            info_message += f"⏱️ Всего дней с ботом: {days_since_first} дней\n\n"
        except:
            pass
    
    if reminder_time:
        timezone = database.get_user_timezone(user_id)
        info_message += f"⏰ Время напоминания: {reminder_time}\n"
        info_message += f"🌍 Часовой пояс: {timezone}\n"
    else:
        info_message += "⏰ Время напоминания: не установлено\n"
    
    keyboard = [
        [InlineKeyboardButton("⏰ Изменить время", callback_data="change_time_btn")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        info_message,
        reply_markup=reply_markup
    )

async def change_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /mur_time или кнопки 'Изменить время'"""
    keyboard = []
    times = [
        ("08:00", "🌅 Утро (8:00)"),
        ("09:00", "🌞 Утро (9:00)"),
        ("10:00", "☀️ Утро (10:00)"),
        ("12:00", "🌤️ Обед (12:00)"),
        ("13:00", "🍽️ Обед (13:00)"),
        ("14:00", "☕ День (14:00)"),
        ("18:00", "🌆 Вечер (18:00)"),
        ("19:00", "🌇 Вечер (19:00)"),
        ("20:00", "🌃 Вечер (20:00)"),
        ("21:00", "🌙 Вечер (21:00)"),
        ("Другое", "⏰ Выбрать другое время")
    ]
    
    for i in range(0, len(times), 2):
        row = []
        row.append(InlineKeyboardButton(times[i][1], callback_data=f"time_{times[i][0]}"))
        if i + 1 < len(times):
            row.append(InlineKeyboardButton(times[i+1][1], callback_data=f"time_{times[i+1][0]}"))
        keyboard.append(row)
    
    # Добавляем кнопку "Настройки" в конец клавиатуры
    keyboard.append([InlineKeyboardButton("⚙️ Настройки", callback_data="settings")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⏰ Выбери новое время для напоминаний:",
        reply_markup=reply_markup
    )
    
    return SELECTING_TIME

async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Настройки'"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    database.log_interaction(user_id, "settings_opened", None, username)
    
    keyboard = [
        [InlineKeyboardButton("🧪 Тест", callback_data="test_notification")],
        [InlineKeyboardButton("🌍 Выбор города", callback_data="select_city")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚙️ Настройки:\n\n"
        "Выбери действие:",
        reply_markup=reply_markup,
        reply_to_message_id=update.message.message_id
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    await update.message.reply_text(
        "Окей, можем выбрать время позже 😊\n"
        "Используй /start чтобы начать заново.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправка напоминания пользователю"""
    user_id = context.job.data
    
    # Проверяем, не выпила ли уже таблеточку сегодня
    if database.is_pill_taken_today(user_id):
        logger.info(f"User {user_id} already took pill today, skipping reminder")
        return
    
    reminder_message = (
        "💊 Выпей таблеточку, малыш. Люблю тебя, хорошего дня! 💕"
    )
    
    # Создаем клавиатуру с кнопкой "Я уже выпила таблеточку"
    keyboard = [
        [InlineKeyboardButton("💖 Я уже выпила таблеточку, любимый", callback_data="pill_taken")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=reminder_message,
            reply_markup=reply_markup
        )
        logger.info(f"Reminder sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error sending reminder to user {user_id}: {e}")

def schedule_reminder(user_id: int, time_str: str, job_queue, timezone: str = 'Europe/Moscow'):
    """Планирует ежедневное напоминание"""
    if job_queue is None:
        logger.warning(f"JobQueue is not available, cannot schedule reminder for user {user_id}")
        return
    
    hour, minute = map(int, time_str.split(':'))
    
    # Удаляем старую задачу если она существует
    job_id = f"reminder_{user_id}"
    # Получаем все задачи и находим нужную по имени
    jobs = job_queue.jobs()
    for job in jobs:
        if job.name == job_id:
            job.schedule_removal()
    
    # Сохраняем параметры для использования в замыкании
    user_tz_obj = pytz.timezone(timezone)
    
    # Создаем обертку, которая планирует следующее напоминание
    async def reminder_with_reschedule(context: ContextTypes.DEFAULT_TYPE):
        """Отправляет напоминание и планирует следующее"""
        logger.info(f"Reminder triggered for user {user_id}")
        await send_reminder(context)
        
        # Планируем следующее напоминание на завтра в то же время
        # Используем сохраненные значения из замыкания
        now_user_tz = datetime.now(user_tz_obj)
        next_time_user_tz = now_user_tz.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=1)
        next_time_utc = next_time_user_tz.astimezone(pytz.UTC)
        delay = (next_time_utc - datetime.now(pytz.UTC)).total_seconds()
        
        logger.info(f"Rescheduling reminder for user {user_id}: next_time_utc={next_time_utc}, delay={delay} seconds")
        
        if delay > 0:
            job_queue.run_once(
                reminder_with_reschedule,
                when=delay,
                data=user_id,
                name=job_id
            )
            logger.info(f"Next reminder scheduled successfully for user {user_id}")
        else:
            logger.warning(f"Cannot reschedule reminder for user {user_id}: delay is {delay} seconds (non-positive)")
    
    # Вычисляем время в UTC, которое соответствует нужному времени в часовом поясе пользователя
    now_user_tz = datetime.now(user_tz_obj)
    target_time_user_tz = now_user_tz.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Если время уже прошло сегодня, планируем на завтра
    if target_time_user_tz <= now_user_tz:
        target_time_user_tz += timedelta(days=1)
    
    # Конвертируем в UTC для планирования
    target_time_utc = target_time_user_tz.astimezone(pytz.UTC)
    
    # Вычисляем задержку до первого запуска
    delay = (target_time_utc - datetime.now(pytz.UTC)).total_seconds()
    
    logger.info(f"Scheduling reminder for user {user_id}: time={time_str}, timezone={timezone}, "
                f"target_time_utc={target_time_utc}, delay={delay} seconds")
    
    if delay > 0:
        job_queue.run_once(
            reminder_with_reschedule,
            when=delay,
            data=user_id,
            name=job_id
        )
        logger.info(f"Reminder scheduled successfully for user {user_id} with delay {delay} seconds")
    else:
        logger.warning(f"Cannot schedule reminder for user {user_id}: delay is {delay} seconds (non-positive)")
    
    logger.info(f"Scheduled reminder for user {user_id} at {time_str} ({timezone})")

def load_existing_reminders(job_queue):
    """Загружает существующие напоминания из базы данных при запуске"""
    if job_queue is None:
        logger.warning("JobQueue is not available, skipping reminder loading")
        return
    
    users = database.get_all_users_with_reminders()
    for user_data in users:
        if len(user_data) >= 3:
            user_id, reminder_time, timezone = user_data[0], user_data[1], user_data[2]
        elif len(user_data) == 2:
            # Совместимость со старыми данными
            user_id, reminder_time = user_data[0], user_data[1]
            timezone = 'Europe/Moscow'
            # Обновляем запись, добавляя часовой пояс
            database.set_reminder_time(user_id, reminder_time, timezone)
        else:
            continue
        schedule_reminder(user_id, reminder_time, job_queue, timezone)
    logger.info(f"Loaded {len(users)} existing reminders")

def main():
    """Главная функция для запуска бота"""
    # Инициализация базы данных
    database.init_database()
    
    # Создание приложения
    application = Application.builder().token(config.BOT_TOKEN).build()

    def is_admin(user_id: int) -> bool:
        return user_id in getattr(config, 'ADMIN_USER_IDS', set())

    async def admin_voice_upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админ отправляет voice -> сохраняем как памятку"""
        if not update.message or not update.message.voice:
            return
        user_id = update.effective_user.id
        if not is_admin(user_id):
            return

        file_id = update.message.voice.file_id
        memo_id = database.add_voice_memo(file_id)

        username = update.effective_user.username or update.effective_user.first_name
        database.log_interaction(user_id, "voice_memo_added", str(memo_id), username)

        await update.message.reply_text(
            f"✅ Памятка сохранена (id={memo_id}).\n"
            f"Теперь можно нажать «{MEMO_BUTTON_TEXT}», чтобы получить следующую памятку."
        )

    async def send_next_voice_memo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Пользователь нажал кнопку -> отправляем следующую памятку (1 раз каждую)."""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name

        memo = database.get_next_voice_memo_for_user(user_id)
        if not memo:
            total, delivered, remaining = database.get_voice_memo_stats_for_user(user_id)
            database.log_interaction(user_id, "voice_memo_empty", f"total={total};delivered={delivered}", username)
            await update.message.reply_text(
                "📭 Памятки закончились для тебя.\n"
                "Если я добавлю новые — кнопка снова начнет выдавать их по одной."
            )
            return

        memo_id, file_id, created_at = memo

        await context.bot.send_voice(chat_id=user_id, voice=file_id)
        database.mark_voice_memo_delivered(user_id, memo_id)
        database.log_interaction(user_id, "voice_memo_delivered", str(memo_id), username)

    # Ловим voice от админа (загрузка памяток)
    application.add_handler(MessageHandler(filters.VOICE, admin_voice_upload_handler), group=0)
    
    # Обработчики для постоянных кнопок меню (добавляем ПЕРЕД ConversationHandler)
    async def button_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых кнопок меню"""
        text = update.message.text
        
        if text == "⏰ Изменить время":
            return await change_time(update, context)
        elif text == "⚙️ Настройки":
            await settings_handler(update, context)
            # Возвращаем ConversationHandler.END чтобы завершить текущий диалог
            return ConversationHandler.END
        elif text == "ℹ️ Информация":
            await info_handler(update, context)
            # Возвращаем ConversationHandler.END чтобы завершить текущий диалог
            return ConversationHandler.END
        elif text == MEMO_BUTTON_TEXT:
            await send_next_voice_memo_handler(update, context)
            return ConversationHandler.END
        elif text == "🏠 Главное меню":
            # Возвращаемся к главному меню
            keyboard = []
            times = [
                ("08:00", "🌅 Утро (8:00)"),
                ("09:00", "🌞 Утро (9:00)"),
                ("10:00", "☀️ Утро (10:00)"),
                ("12:00", "🌤️ Обед (12:00)"),
                ("13:00", "🍽️ Обед (13:00)"),
                ("14:00", "☕ День (14:00)"),
                ("18:00", "🌆 Вечер (18:00)"),
                ("19:00", "🌇 Вечер (19:00)"),
                ("20:00", "🌃 Вечер (20:00)"),
                ("21:00", "🌙 Вечер (21:00)"),
                ("Другое", "⏰ Выбрать другое время")
            ]
            for i in range(0, len(times), 2):
                row = []
                row.append(InlineKeyboardButton(times[i][1], callback_data=f"time_{times[i][0]}"))
                if i + 1 < len(times):
                    row.append(InlineKeyboardButton(times[i+1][1], callback_data=f"time_{times[i+1][0]}"))
                keyboard.append(row)
            keyboard.append([InlineKeyboardButton("⚙️ Настройки", callback_data="settings")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "💊 Главное меню 💕\n\n"
                "Выбери время, когда тебе удобно получать напоминания: ⏰",
                reply_markup=reply_markup
            )
            return SELECTING_TIME
    
    # Обработчик для пользовательского времени (работает вне ConversationHandler)
    async def handle_custom_time_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик пользовательского времени, работающий вне ConversationHandler"""
        user_id = update.effective_user.id
        text = update.message.text if update.message else None
        logger.info(f"handle_custom_time_global called for user {user_id}, text: {text}, waiting_for_custom_time: {context.user_data.get('waiting_for_custom_time')}")
        
        # Проверяем, ожидается ли пользовательский ввод времени
        if not context.user_data.get('waiting_for_custom_time'):
            logger.info(f"handle_custom_time_global: waiting_for_custom_time is False for user {user_id}, skipping")
            return  # Если флаг не установлен, ничего не делаем
        
        # Если флаг установлен, обрабатываем пользовательский ввод
        logger.info(f"handle_custom_time_global: processing custom time input from user {update.effective_user.id}")
        user_id = update.effective_user.id
        time_str = update.message.text.strip()
        
        # Проверяем формат времени
        try:
            hour, minute = map(int, time_str.split(':'))
            if 0 <= hour < 24 and 0 <= minute < 60:
                time_formatted = f"{hour:02d}:{minute:02d}"
                timezone = database.get_user_timezone(user_id)
                # При смене времени очищаем отметку о выпитой таблеточке сегодня
                database.clear_pill_taken_today(user_id)
                username = update.effective_user.username or update.effective_user.first_name
                database.set_reminder_time(user_id, time_formatted, timezone, username)
                database.log_interaction(user_id, "reminder_time_changed", time_formatted, username)
                logger.info(f"User {user_id} entered custom time {time_formatted} in timezone {timezone}")
                schedule_reminder(user_id, time_formatted, context.application.job_queue, timezone)
                
                # Сбрасываем флаг
                context.user_data['waiting_for_custom_time'] = False
                
                keyboard = [
                    [InlineKeyboardButton("⏰ Изменить время", callback_data="change_time_btn")],
                    [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
                    [InlineKeyboardButton("ℹ️ Информация", callback_data="info_btn")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"✅ Отлично, малыш! 💕\n\n"
                    f"Я буду напоминать тебе каждый день в {time_formatted} ⏰\n\n"
                    f"Не забудь выпить таблеточку! 💊",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    "❌ Время указано неверно. Укажи часы от 0 до 23 и минуты от 0 до 59.\n"
                    "Попробуй еще раз (формат ЧЧ:ММ):"
                )
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат времени. Напиши время в формате ЧЧ:ММ (например, 15:30):"
            )
        except Exception as e:
            logger.error(f"Error handling custom time: {e}", exc_info=True)
            await update.message.reply_text("❌ Произошла ошибка при обработке времени. Попробуй еще раз.")
            context.user_data['waiting_for_custom_time'] = False
    
    # Добавляем обработчик для пользовательского времени ПЕРЕД обработчиком постоянных кнопок
    # Используем group=-1 чтобы он обрабатывался ДО ConversationHandler
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_custom_time_global
    ), group=-1)
    
    # Добавляем обработчик для постоянных кнопок ПЕРЕД ConversationHandler
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex('^(⏰ Изменить время|⚙️ Настройки|ℹ️ Информация|🏠 Главное меню|🎧 Получить памятку)$'),
        button_text_handler
    ), group=1)
    
    
    # Создание ConversationHandler для обработки выбора времени
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('Start', start),
            CommandHandler('START', start),
            CommandHandler('mur', start),
            CommandHandler('mur_time', change_time),
            MessageHandler(filters.Regex('^⏰ Изменить время$'), change_time)
        ],
        states={
            SELECTING_TIME: [
                # Убираем select_city и city_ из паттерна, чтобы они обрабатывались глобальным обработчиком
                CallbackQueryHandler(button_callback, pattern='^(time_|settings|test_notification|back_to_main|change_time_btn|info_btn|main_menu)')
            ],
            CONFIRMING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_time)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Отдельный обработчик для кнопки "Я уже выпила таблеточку" (работает всегда, добавляем ПЕРЕД conv_handler)
    async def pill_taken_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Я уже выпила таблеточку'"""
        query = update.callback_query
        if query and query.data == "pill_taken":
            await query.answer()
            user_id = query.from_user.id
            from datetime import date
            today = date.today().isoformat()
            username = query.from_user.username or query.from_user.first_name
            database.mark_pill_taken(user_id, today)
            database.log_interaction(user_id, "pill_taken", today, username)
            
            keyboard = [
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "💕 Отлично, малыш! Горжусь тобой! Сегодня напоминание больше не придет. 😊💖",
                reply_markup=reply_markup
            )
    
    application.add_handler(CallbackQueryHandler(pill_taken_callback, pattern='^pill_taken$'))
    
    # Отдельный обработчик для inline кнопок, которые работают всегда (вне ConversationHandler)
    async def global_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Глобальный обработчик inline кнопок, работающий всегда"""
        query = update.callback_query
        if not query:
            return
        
        await query.answer()
        data = query.data
        logger.info(f"Global button callback received: {data} from user {query.from_user.id}")
        
        # Обрабатываем кнопки, которые должны работать вне ConversationHandler
        if data == "change_time_btn":
            # Открываем меню выбора времени
            keyboard = []
            times = [
                ("08:00", "🌅 Утро (8:00)"),
                ("09:00", "🌞 Утро (9:00)"),
                ("10:00", "☀️ Утро (10:00)"),
                ("12:00", "🌤️ Обед (12:00)"),
                ("13:00", "🍽️ Обед (13:00)"),
                ("14:00", "☕ День (14:00)"),
                ("18:00", "🌆 Вечер (18:00)"),
                ("19:00", "🌇 Вечер (19:00)"),
                ("20:00", "🌃 Вечер (20:00)"),
                ("21:00", "🌙 Вечер (21:00)"),
                ("Другое", "⏰ Выбрать другое время")
            ]
            for i in range(0, len(times), 2):
                row = []
                row.append(InlineKeyboardButton(times[i][1], callback_data=f"time_{times[i][0]}"))
                if i + 1 < len(times):
                    row.append(InlineKeyboardButton(times[i+1][1], callback_data=f"time_{times[i+1][0]}"))
                keyboard.append(row)
            keyboard.append([InlineKeyboardButton("⚙️ Настройки", callback_data="settings")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.edit_message_text(
                    "💊 Выбери время, когда тебе удобно получать напоминания: ⏰",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                await query.message.reply_text(
                    "💊 Выбери время, когда тебе удобно получать напоминания: ⏰",
                    reply_markup=reply_markup
                )
        elif data == "settings":
            # Показываем настройки
            username = query.from_user.username or query.from_user.first_name
            database.log_interaction(query.from_user.id, "settings_opened", None, username)
            keyboard = [
                [InlineKeyboardButton("🧪 Тест", callback_data="test_notification")],
                [InlineKeyboardButton("🌍 Выбор города", callback_data="select_city")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.edit_message_text(
                    "⚙️ Настройки:\n\n"
                    "Выбери действие:",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                await query.message.reply_text(
                    "⚙️ Настройки:\n\n"
                    "Выбери действие:",
                    reply_markup=reply_markup
                )
        elif data == "info_btn":
            # Показываем информацию
            user_id = query.from_user.id
            username = query.from_user.username or query.from_user.first_name
            database.log_interaction(user_id, "info_viewed", None, username)
            
            days_count = database.get_days_count(user_id)
            first_date = database.get_first_use_date(user_id)
            reminder_time = database.get_reminder_time(user_id)
            
            info_message = (
                f"ℹ️ Информация о твоем использовании бота:\n\n"
                f"📊 Количество дней, когда ты пила таблеточку с помощью бота: {days_count} дней\n\n"
            )
            
            if first_date:
                try:
                    first_dt = datetime.fromisoformat(first_date)
                    days_since_first = (datetime.now().date() - first_dt.date()).days + 1
                    info_message += f"📅 Первое использование: {first_dt.strftime('%d.%m.%Y')}\n"
                    info_message += f"⏱️ Всего дней с ботом: {days_since_first} дней\n\n"
                except:
                    pass
            
            if reminder_time:
                timezone = database.get_user_timezone(user_id)
                info_message += f"⏰ Время напоминания: {reminder_time}\n"
                info_message += f"🌍 Часовой пояс: {timezone}\n"
            else:
                info_message += "⏰ Время напоминания: не установлено\n"
            
            keyboard = [
                [InlineKeyboardButton("⏰ Изменить время", callback_data="change_time_btn")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.edit_message_text(
                    info_message,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Error editing message for info: {e}")
                await query.message.reply_text(
                    info_message,
                    reply_markup=reply_markup
                )
        elif data == "back_to_main" or data == "main_menu":
            # Сбрасываем флаг ожидания пользовательского времени
            if 'waiting_for_custom_time' in context.user_data:
                context.user_data['waiting_for_custom_time'] = False
            # Возвращаемся к главному меню
            keyboard = []
            times = [
                ("08:00", "🌅 Утро (8:00)"),
                ("09:00", "🌞 Утро (9:00)"),
                ("10:00", "☀️ Утро (10:00)"),
                ("12:00", "🌤️ Обед (12:00)"),
                ("13:00", "🍽️ Обед (13:00)"),
                ("14:00", "☕ День (14:00)"),
                ("18:00", "🌆 Вечер (18:00)"),
                ("19:00", "🌇 Вечер (19:00)"),
                ("20:00", "🌃 Вечер (20:00)"),
                ("21:00", "🌙 Вечер (21:00)"),
                ("Другое", "⏰ Выбрать другое время")
            ]
            for i in range(0, len(times), 2):
                row = []
                row.append(InlineKeyboardButton(times[i][1], callback_data=f"time_{times[i][0]}"))
                if i + 1 < len(times):
                    row.append(InlineKeyboardButton(times[i+1][1], callback_data=f"time_{times[i+1][0]}"))
                keyboard.append(row)
            keyboard.append([InlineKeyboardButton("⚙️ Настройки", callback_data="settings")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.edit_message_text(
                    "💊 Главное меню 💕\n\n"
                    "Выбери время, когда тебе удобно получать напоминания: ⏰",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                await query.message.reply_text(
                    "💊 Главное меню 💕\n\n"
                    "Выбери время, когда тебе удобно получать напоминания: ⏰",
                    reply_markup=reply_markup
                )
        elif data.startswith("time_"):
            # Обработка выбора времени
            logger.info(f"Time button pressed: {data} from user {query.from_user.id}")
            time_str = data[5:]  # Убираем префикс "time_"
            
            if time_str == "Другое":
                # Устанавливаем флаг ожидания пользовательского времени
                context.user_data['waiting_for_custom_time'] = True
                logger.info(f"Set waiting_for_custom_time=True for user {query.from_user.id}")
                keyboard = [
                    [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                try:
                    await query.edit_message_text(
                        "💭 Напиши время в формате ЧЧ:ММ (например, 15:30 или 09:15):",
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Error editing message: {e}")
                    await query.message.reply_text(
                        "💭 Напиши время в формате ЧЧ:ММ (например, 15:30 или 09:15):",
                        reply_markup=reply_markup
                    )
            else:
                # Обрабатываем выбранное время
                try:
                    hour, minute = map(int, time_str.split(':'))
                    if 0 <= hour < 24 and 0 <= minute < 60:
                        user_id = query.from_user.id
                        timezone = database.get_user_timezone(user_id)
                        username = query.from_user.username or query.from_user.first_name
                        # При смене времени очищаем отметку о выпитой таблеточке сегодня
                        database.clear_pill_taken_today(user_id)
                        database.set_reminder_time(user_id, time_str, timezone, username)
                        database.log_interaction(user_id, "reminder_time_changed", time_str, username)
                        logger.info(f"User {user_id} selected time {time_str} in timezone {timezone}")
                        schedule_reminder(user_id, time_str, context.application.job_queue, timezone)
                        
                        keyboard = [
                            [InlineKeyboardButton("⏰ Изменить время", callback_data="change_time_btn")],
                            [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
                            [InlineKeyboardButton("ℹ️ Информация", callback_data="info_btn")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        try:
                            await query.edit_message_text(
                                f"✅ Отлично, малыш! 💕\n\n"
                                f"Я буду напоминать тебе каждый день в {time_str} ⏰\n\n"
                                f"Не забудь выпить таблеточку! 💊",
                                reply_markup=reply_markup
                            )
                        except Exception as e:
                            logger.error(f"Error editing message: {e}")
                            await query.message.reply_text(
                                f"✅ Отлично, малыш! 💕\n\n"
                                f"Я буду напоминать тебе каждый день в {time_str} ⏰\n\n"
                                f"Не забудь выпить таблеточку! 💊",
                                reply_markup=reply_markup
                            )
                    else:
                        keyboard = [
                            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        try:
                            await query.edit_message_text(
                                "❌ Время указано неверно. Попробуй еще раз:",
                                reply_markup=reply_markup
                            )
                        except Exception as e:
                            logger.error(f"Error editing message: {e}")
                            await query.message.reply_text(
                                "❌ Время указано неверно. Попробуй еще раз:",
                                reply_markup=reply_markup
                            )
                except ValueError as e:
                    logger.error(f"Error parsing time {time_str}: {e}")
                    keyboard = [
                        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    try:
                        await query.edit_message_text(
                            "❌ Неверный формат времени. Попробуй еще раз.",
                            reply_markup=reply_markup
                        )
                    except Exception as e2:
                        logger.error(f"Error editing message: {e2}")
                        await query.message.reply_text(
                            "❌ Неверный формат времени. Попробуй еще раз.",
                            reply_markup=reply_markup
                        )
        elif data == "test_notification":
            # Тестовое уведомление
            username = query.from_user.username or query.from_user.first_name
            database.log_interaction(query.from_user.id, "test_notification", None, username)
            reminder_message = "💊 Выпей таблеточку, малыш. Люблю тебя, хорошего дня! 💕"
            keyboard = [
                [InlineKeyboardButton("💖 Я уже выпила таблеточку, любимый", callback_data="pill_taken")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="settings")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.edit_message_text(reminder_message, reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                await query.message.reply_text(reminder_message, reply_markup=reply_markup)
        elif data == "select_city":
            # Выбор города
            logger.info(f"select_city button pressed by user {query.from_user.id}")
            keyboard = [
                [InlineKeyboardButton("🏙️ Санкт-Петербург (UTC+3)", callback_data="city_spb")],
                [InlineKeyboardButton("🏔️ Уфа (UTC+5)", callback_data="city_ufa")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="settings")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.edit_message_text(
                    "🌍 Выбери город для установки часового пояса:",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}", exc_info=True)
                await query.message.reply_text(
                    "🌍 Выбери город для установки часового пояса:",
                    reply_markup=reply_markup
                )
        elif data == "city_spb" or data == "city_ufa":
            # Установка часового пояса
            logger.info(f"City button pressed: {data} by user {query.from_user.id}")
            user_id = query.from_user.id
            if data == "city_spb":
                timezone = 'Europe/Moscow'
                city_name = "Санкт-Петербург (UTC+3)"
            else:
                timezone = 'Asia/Yekaterinburg'
                city_name = "Уфа (UTC+5)"
            
            username = query.from_user.username or query.from_user.first_name
            database.set_user_timezone(user_id, timezone, username)
            database.log_interaction(user_id, "timezone_changed", city_name, username)
            
            # Перепланируем напоминание с новым часовым поясом
            reminder_time = database.get_reminder_time(user_id)
            if reminder_time:
                schedule_reminder(user_id, reminder_time, context.application.job_queue, timezone)
            
            try:
                await query.edit_message_text(
                    f"✅ Часовой пояс изменен на {city_name} 🌍\n\n"
                    f"Напоминания теперь будут приходить согласно этому часовому поясу. 💕"
                )
                logger.info(f"Timezone changed to {city_name} for user {user_id}")
            except Exception as e:
                logger.error(f"Error editing message: {e}", exc_info=True)
                await query.message.reply_text(
                    f"✅ Часовой пояс изменен на {city_name} 🌍\n\n"
                    f"Напоминания теперь будут приходить согласно этому часовому поясу. 💕"
                )
    
    # Добавляем глобальный обработчик для inline кнопок (добавляем ПЕРЕД ConversationHandler)
    # Включаем обработку кнопок времени (time_*), чтобы они работали всегда
    application.add_handler(CallbackQueryHandler(global_button_callback, pattern='^(change_time_btn|settings|info_btn|back_to_main|main_menu|time_|test_notification|select_city|city_)'))
    
    # Тестовая команда для проверки напоминаний
    async def test_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестовая команда для проверки отправки напоминания"""
        user_id = update.effective_user.id
        reminder_message = (
            "💊 Выпей таблеточку, малыш. Люблю тебя, хорошего дня! 💕"
        )
        
        # Создаем клавиатуру с кнопкой "Я уже выпила таблеточку"
        keyboard = [
            [InlineKeyboardButton("💖 Я уже выпила таблеточку, любимый", callback_data="pill_taken")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            reminder_message,
            reply_markup=reply_markup
        )
    
    application.add_handler(CommandHandler('test', test_reminder))
    
    # Команда для экспорта данных в Excel
    async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для экспорта данных в Excel"""
        try:
            import excel_export
            filename = excel_export.export_to_excel()
            
            # Отправляем файл пользователю
            with open(filename, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=filename,
                    caption="📊 Вот твои данные из базы бота! 📈\n\n"
                            "Файл содержит:\n"
                            "• Информацию о пользователях\n"
                            "• Историю взаимодействий\n"
                            "• Данные о принятых таблеточках"
                )
            
            # Удаляем временный файл
            import os
            os.remove(filename)
            
            user_id = update.effective_user.id
            username = update.effective_user.username or update.effective_user.first_name
            database.log_interaction(user_id, "data_exported", None, username)
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            await update.message.reply_text(f"❌ Ошибка при экспорте данных: {e}")
    
    application.add_handler(CommandHandler('export', export_data))
    
    
    # Добавление обработчиков
    application.add_handler(conv_handler)
    
    # Логируем количество зарегистрированных обработчиков
    logger.info(f"Total handlers registered: {len(application.handlers[0])}")
    
    # Загрузка существующих напоминаний через post_init
    async def post_init(app: Application) -> None:
        """Загружает существующие напоминания после инициализации"""
        load_existing_reminders(app.job_queue)
        logger.info("Existing reminders loaded")
    
    application.post_init = post_init
    
    # Запуск бота
    logger.info("Bot is starting...")
    logger.info("Handlers registered, starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

def create_and_setup_application():
    """
    Создает и настраивает Application со всеми обработчиками.
    Возвращает настроенное приложение.
    Эта функция содержит всю логику настройки из main(), но без запуска.
    """
    # Инициализация базы данных
    database.init_database()
    
    # Создание приложения
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Вся логика настройки обработчиков находится в main()
    # Чтобы избежать дублирования кода, вызовем main() с переопределением run_polling
    # Но это сложно. Лучше скопировать логику настройки сюда
    
    # Пока возвращаем application, а настройку делаем через вызов main
    # Это не идеально, но работает
    return application

async def run_bot_with_start_polling():
    """
    Запускает бота используя start() и start_polling() вместо run_polling().
    Это работает в отдельном потоке без проблем с сигналами.
    """
    # Инициализация базы данных
    database.init_database()
    
    # Создание приложения
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Настройка обработчиков - нужно вызвать ту же логику, что в main()
    # Но так как она находится внутри main(), используем другой подход:
    # Вызовем main() но переопределим Application.run_polling перед этим
    
    # Временно: просто вызываем main(), но в отдельном потоке это вызовет ошибку
    # Нужно вынести настройку в отдельную функцию
    
    # Загрузка существующих напоминаний через post_init
    async def post_init(app: Application) -> None:
        """Загружает существующие напоминания после инициализации"""
        load_existing_reminders(app.job_queue)
        logger.info("Existing reminders loaded")
    
    application.post_init = post_init
    
    # Запускаем через start() и start_polling()
    async with application:
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES, 
            drop_pending_updates=True
        )
        logger.info("Bot is running...")
        
        # Ожидаем бесконечно (без обработки сигналов)
        import asyncio
        stop_event = asyncio.Event()
        await stop_event.wait()

if __name__ == '__main__':
    main()
