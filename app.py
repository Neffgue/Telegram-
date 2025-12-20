"""
WSGI приложение для хостинга
Запускает веб-сервер для health checks и бота в отдельном потоке
"""
import threading
import logging
from flask import Flask

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаем Flask приложение
app = Flask(__name__)

@app.route('/')
def health_check():
    """Health check endpoint для хостинга"""
    return {'status': 'ok', 'message': 'Telegram bot is running'}, 200

@app.route('/health')
def health():
    """Дополнительный health check endpoint"""
    return {'status': 'healthy'}, 200

def run_bot():
    """Запускает бота в отдельном потоке"""
    try:
        import bot
        bot.main()
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

# Запускаем бота в отдельном потоке при старте приложения
bot_thread = None

def start_bot():
    """Запускает бота в фоновом потоке"""
    global bot_thread
    if bot_thread is None or not bot_thread.is_alive():
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        logger.info("Bot thread started")

# Запускаем бота при импорте модуля (для WSGI серверов)
start_bot()

if __name__ == '__main__':
    # Если запускается напрямую, запускаем Flask сервер
    logger.info("Starting Flask server and bot...")
    start_bot()
    app.run(host='0.0.0.0', port=8080, debug=False)


