"""
WSGI приложение для хостинга
Запускает веб-сервер и бота в отдельном потоке
"""
import threading
import logging
import asyncio
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

def run_bot_in_thread():
    """Запускает бота в отдельном потоке"""
    try:
        from telegram.ext import Application
        import bot
        import config
        
        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Переопределяем run_polling для работы без обработки сигналов
        original_run_polling = Application.run_polling
        
        def patched_run_polling(self, *args, **kwargs):
            """Патч для run_polling, который работает в отдельном потоке"""
            async def run():
                async with self:
                    await self.start()
                    # Явно вызываем post_init если он установлен
                    if hasattr(self, 'post_init') and self.post_init:
                        await self.post_init(self)
                    await self.updater.start_polling(*args, **kwargs)
                    logger.info("Bot is running in thread...")
                    # Ожидаем бесконечно без обработки сигналов
                    stop_event = asyncio.Event()
                    await stop_event.wait()
            
            try:
                loop.run_until_complete(run())
            except KeyboardInterrupt:
                logger.info("Bot stopping...")
            except Exception as e:
                logger.error(f"Error in bot: {e}", exc_info=True)
        
        # Применяем патч перед импортом bot.main
        Application.run_polling = patched_run_polling
        
        # Теперь вызываем main, который создаст application и вызовет run_polling
        # Патч сработает для всех экземпляров Application
        bot.main()
        
    except Exception as e:
        logger.error(f"Error running bot: {e}", exc_info=True)
        import traceback
        traceback.print_exc()

# Запускаем бота в отдельном потоке
bot_thread = None

def start_bot():
    """Запускает бота в фоновом потоке"""
    global bot_thread
    if bot_thread is None or not bot_thread.is_alive():
        bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()
        logger.info("Bot thread started")

# Запускаем бота при импорте модуля (для WSGI серверов)
start_bot()

if __name__ == '__main__':
    # Если запускается напрямую, запускаем Flask сервер
    logger.info("Starting Flask server and bot...")
    start_bot()
    app.run(host='0.0.0.0', port=8080, debug=False)
