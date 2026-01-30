"""Админ-команды для управления голосовыми памятками и резервным копированием/восстановлением базы."""

from __future__ import annotations

import os
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

import config
import database


def is_admin(user_id: int) -> bool:
    return user_id in getattr(config, "ADMIN_USER_IDS", set())


def _format_dt_iso(iso_str: str) -> str:
    try:
        return datetime.fromisoformat(iso_str).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso_str


async def cmd_memos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/memos [N] — показать последние N памяток."""
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    limit = 10
    if context.args:
        try:
            limit = int(context.args[0])
        except ValueError:
            limit = 10

    limit = max(1, min(limit, 50))
    memos = database.list_voice_memos(limit=limit)

    if not memos:
        await update.message.reply_text("Памяточек пока нет.")
        return

    lines = [f"Последние {len(memos)} памяточек (новые сверху):"]
    for memo_id, _file_id, created_at in memos:
        lines.append(f"• id={memo_id} — {_format_dt_iso(created_at)}")

    lines.append("\nУдаление: /memo_delete <id>")
    await update.message.reply_text("\n".join(lines))


async def cmd_memo_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/memo_delete <id> — удалить памятку по id."""
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text("Использование: /memo_delete <id>")
        return

    try:
        memo_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("id должен быть числом. Пример: /memo_delete 12")
        return

    ok = database.delete_voice_memo(memo_id)
    if ok:
        await update.message.reply_text(f"✅ Удалил памяточку id={memo_id}.")
    else:
        await update.message.reply_text(f"Не нашёл памяточку id={memo_id}.")


async def cmd_db_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/db_backup — отправить текущий файл базы администратору."""
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db_path = database.DATABASE_NAME
    if not os.path.exists(db_path):
        await update.message.reply_text("Файл базы не найден.")
        return

    try:
        with open(db_path, "rb") as f:
            await update.message.reply_document(document=f, filename=os.path.basename(db_path))
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось отправить базу: {e}")


async def cmd_db_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/db_restore — включить режим восстановления: ждём .db файлом."""
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    context.user_data["waiting_for_db_restore"] = True
    await update.message.reply_text(
        "Отправь мне файлом (document) SQLite базу *.db, и я заменю текущую.\n"
        "Перед заменой сделаю бэкап текущего pillow_bot.db.\n\n"
        "Важно: после восстановления перезапусти бота/контейнер на BotHost."
    )


def _looks_like_sqlite(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            header = f.read(16)
        return header.startswith(b"SQLite format 3\x00")
    except Exception:
        return False


async def handle_db_restore_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """При включенном /db_restore принимает document и заменяет DB."""
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.user_data.get("waiting_for_db_restore"):
        return

    doc = update.message.document
    if not doc:
        return

    filename = (doc.file_name or "").lower()
    if filename and not filename.endswith(".db"):
        await update.message.reply_text("Пожалуйста, пришли файл с расширением .db")
        return

    upload_path = f"{database.DATABASE_NAME}.upload"

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(custom_path=upload_path)

        if not _looks_like_sqlite(upload_path):
            try:
                os.remove(upload_path)
            except Exception:
                pass
            await update.message.reply_text("Файл не похож на SQLite базу. Отмена.")
            return

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        db_path = database.DATABASE_NAME
        backup_path = f"{db_path}.backup-{ts}.db"

        if os.path.exists(db_path):
            os.replace(db_path, backup_path)

        os.replace(upload_path, db_path)

        # На всякий случай создаём недостающие таблицы
        database.init_database()

        context.user_data["waiting_for_db_restore"] = False

        await update.message.reply_text(
            f"✅ База восстановлена. Старый файл сохранён как {os.path.basename(backup_path)}.\n"
            "Перезапусти бота/контейнер на BotHost."
        )

    except Exception as e:
        try:
            if os.path.exists(upload_path):
                os.remove(upload_path)
        except Exception:
            pass
        await update.message.reply_text(f"❌ Ошибка восстановления базы: {e}")
