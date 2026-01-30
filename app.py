"""WSGI приложение для хостинга.

Поднимает Flask (health endpoints) и запускает Telegram-бота в отдельном потоке.
Дополнительно "подмешивает" админ-команды (без правок в bot.py), чтобы:
- /memos [N] — список последних памяток
- /memo_delete <id> — удалить памятку
- /db_backup — отправить текущий pillow_bot.db
- /db_restore — включить режим восстановления, затем отправить .db файлом
"""

import asyncio
import logging
import threading

from flask import Flask

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route('/')
def health_check():
    return {'status': 'ok', 'message': 'Telegram bot is running'}, 200


@app.route('/health')
def health():
    return {'status': 'healthy'}, 200


_bot_started = False
_lock = threading.Lock()


def run_bot_in_thread():
    """Запускает бота в отдельном потоке (без signal handlers)."""
    try:
        from telegram.ext import Application, CommandHandler, MessageHandler, filters

        import bot
        import admin_tools

        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 1) Внедряем админские handlers в каждый Application, созданный через Application.builder().build()
        original_builder = Application.builder

        def patched_builder(*args, **kwargs):
            builder = original_builder(*args, **kwargs)
            original_build = builder.build

            def patched_build(*b_args, **b_kwargs):
                application = original_build(*b_args, **b_kwargs)

                application.add_handler(CommandHandler('memos', admin_tools.cmd_memos))
                application.add_handler(CommandHandler('memo_delete', admin_tools.cmd_memo_delete))
                application.add_handler(CommandHandler('db_backup', admin_tools.cmd_db_backup))
                application.add_handler(CommandHandler('db_restore', admin_tools.cmd_db_restore))
                application.add_handler(
                    MessageHandler(filters.Document.ALL, admin_tools.handle_db_restore_document),
                    group=0
                )

                return application

            builder.build = patched_build
            return builder

        Application.builder = patched_builder

        # 2) Патчим run_polling, чтобы не пытался регистрировать сигналы (в thread это падает)
        def patched_run_polling(self, *args, **kwargs):
            async def runner():
                async with self:
                    await self.start()

                    # post_init используется в bot.py для загрузки напоминаний
                    if getattr(self, 'post_init', None):
                        await self.post_init(self)

                    await self.updater.start_polling(*args, **kwargs)
                    logger.info('Bot is running in thread...')

                    stop_event = asyncio.Event()
                    await stop_event.wait()

            loop = asyncio.get_event_loop()
            loop.run_until_complete(runner())

        Application.run_polling = patched_run_polling

        # Запускаем исходный bot.main() — он создаст Application и вызовет run_polling()
        bot.main()

    except Exception as e:
        logger.error(f'Bot thread crashed: {e}', exc_info=True)


def _ensure_bot_started():
    global _bot_started
    with _lock:
        if _bot_started:
            return
        t = threading.Thread(target=run_bot_in_thread, daemon=True)
        t.start()
        _bot_started = True


# Стартуем бота при импорте модуля (обычно 1 раз на процесс)
_ensure_bot_started()
