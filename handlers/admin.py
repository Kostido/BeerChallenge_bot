import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, MessageHandler, filters
from db_utils import get_db, get_leaderboard, add_or_update_user
from models import User, BeerEntry
import os
from sqlalchemy import func
import re

# Добавляем логгер
logger = logging.getLogger(__name__)

ADMIN_PASSWORD = os.environ.get("AdminPass")  # Теперь пароль берется из переменной окружения
AWAITING_PASSWORD, AWAITING_USER_ID, AWAITING_NEW_VOLUME, AWAITING_SUBMISSION_USER = range(4)
AWAITING_ENTRY_ACTION, AWAITING_ACTION_CHOICE, AWAITING_USER_LIST = range(4, 7)

admin_ids = set()  # Временное хранение id админов

async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите пароль администратора:")
    return AWAITING_PASSWORD

async def check_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == ADMIN_PASSWORD:
        admin_ids.add(update.effective_user.id)
        await update.message.reply_text("Режим администратора активирован.\nДоступные команды:\n/change_leaderboard — изменить объем участника\n/check_submission — посмотреть фото участника")
        return ConversationHandler.END
    await update.message.reply_text("Неверный пароль. Попробуйте снова или /cancel.")
    return AWAITING_PASSWORD

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fetches and sends a list of users to the admin for selection."""
    try:
        with next(get_db()) as db:
            users = db.query(User).all()

        if not users:
            await update.message.reply_text("Список участников пуст.")
            return ConversationHandler.END

        user_list_text = "Список участников:\n"
        for user in users:
            # Fetch the total beer volume for each user
            with next(get_db()) as db:
                total_volume = db.query(BeerEntry).filter(BeerEntry.user_id == user.id).with_entities(func.sum(BeerEntry.volume_liters)).scalar()
            user_list_text += f"ID: {user.id}, Имя: {user.first_name}, Объем: {total_volume:.2f} л\n"

        await update.message.reply_text(user_list_text)
        return AWAITING_USER_ID

    except Exception as e:
        logger.error(f"Error fetching users: {e}", exc_info=True)
        await update.message.reply_text("Не удалось загрузить список участников. Попробуйте позже.")
        return ConversationHandler.END

async def change_leaderboard_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("Нет доступа. Введите /admin для входа.")
        return ConversationHandler.END
    await list_users(update, context)
    return AWAITING_USER_ID

async def receive_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['target_user_id'] = update.message.text
    await update.message.reply_text("Введите новый общий объем пива (литры):")
    return AWAITING_NEW_VOLUME

async def receive_new_volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = context.user_data.get('target_user_id')
    try:
        new_volume = float(update.message.text)
        with next(get_db()) as db:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if not user:
                await update.message.reply_text("Пользователь не найден.")
                return ConversationHandler.END
            # Удаляем старые записи и создаём одну новую
            db.query(BeerEntry).filter(BeerEntry.user_id == int(user_id)).delete()
            db.add(BeerEntry(user_id=int(user_id), volume_liters=new_volume, photo_file_id="manual_admin"))
            db.commit()
        await update.message.reply_text(f"Объем для пользователя {user_id} обновлен: {new_volume} л")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
    return ConversationHandler.END

async def check_submission_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("Нет доступа. Введите /admin для входа.")
        return ConversationHandler.END

    # Fetch and display the list of users with their beer volumes
    with next(get_db()) as db:
        users = db.query(User).all()
        if not users:
            await update.message.reply_text("Нет зарегистрированных участников.")
            return ConversationHandler.END

        user_list_text = "Список участников:\n"
        for user in users:
            total_volume = sum(entry.volume_liters for entry in user.beer_entries)
            user_list_text += f"ID: {user.id}, {user.first_name} - {total_volume:.2f} л\n"

        await update.message.reply_text(user_list_text + "\nВведите ID пользователя для просмотра его заявок:")

    return AWAITING_SUBMISSION_USER

async def show_user_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.text
    with next(get_db()) as db:
        entries = db.query(BeerEntry).filter(BeerEntry.user_id == int(user_id)).all()
        if not entries:
            await update.message.reply_text("Нет записей для этого пользователя.")
            return ConversationHandler.END
        entry_list_text = "Выберите запись для изменения или удаления:\n"
        for index, entry in enumerate(entries, start=1):
            entry_list_text += f"{index}. {entry.volume_liters} л, {entry.submitted_at}\n"
        context.user_data['entries'] = entries
        await update.message.reply_text(entry_list_text + "\nВведите номер записи:")
    return AWAITING_ENTRY_ACTION

async def handle_entry_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        entry_index = int(update.message.text) - 1
        entries = context.user_data.get('entries')
        if entries is None or entry_index < 0 or entry_index >= len(entries):
            await update.message.reply_text("Неверный номер записи.")
            return AWAITING_ENTRY_ACTION
        context.user_data['selected_entry'] = entries[entry_index]
        await update.message.reply_text("Введите 'изменить' для изменения или 'удалить' для удаления записи:")
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректный номер.")
    return AWAITING_ACTION_CHOICE

async def update_or_delete_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    action = update.message.text.lower()
    entry = context.user_data.get('selected_entry')
    if action == 'изменить':
        await update.message.reply_text("Введите новый объем пива (литры):")
        return AWAITING_NEW_VOLUME
    elif action == 'удалить':
        with next(get_db()) as db:
            db.delete(entry)
            db.commit()
        await update.message.reply_text("Запись удалена.")
    else:
        await update.message.reply_text("Неверный выбор. Пожалуйста, введите 'изменить' или 'удалить'.")
        return AWAITING_ACTION_CHOICE
    return ConversationHandler.END

async def import_users_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запускает процесс импорта списка пользователей."""
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("Нет доступа. Введите /admin для входа.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Введите список участников в формате:\n\n"
        "ID: 123456789, Имя: Имя_участника, Объем: X.XX л\n"
        "ID: 987654321, Имя: Другой_участник, Объем: Y.YY л\n\n"
        "Каждый участник должен быть на отдельной строке."
    )
    return AWAITING_USER_LIST

async def receive_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает полученный список пользователей и добавляет их в базу данных."""
    user_list_text = update.message.text
    user_lines = user_list_text.strip().split('\n')
    
    successful_imports = 0
    failed_imports = 0
    results = []
    
    # Регулярное выражение для извлечения данных из строки
    pattern = r'ID:\s*(\d+),\s*Имя:\s*([^,]+),\s*Объем:\s*(\d+\.?\d*)\s*л'
    
    for line in user_lines:
        match = re.search(pattern, line)
        if match:
            user_id, name, volume = match.groups()
            
            try:
                user_id = int(user_id)
                volume = float(volume)
                
                with next(get_db()) as db:
                    # Добавляем или обновляем пользователя
                    add_or_update_user(db, user_id=user_id, first_name=name, username=None)
                    
                    # Удаляем существующие записи о пиве для этого пользователя
                    db.query(BeerEntry).filter(BeerEntry.user_id == user_id).delete()
                    
                    # Добавляем новую запись с указанным объемом
                    db.add(BeerEntry(user_id=user_id, volume_liters=volume, photo_file_id="imported_by_admin"))
                    db.commit()
                
                results.append(f"✅ ID: {user_id}, Имя: {name}, Объем: {volume:.2f} л")
                successful_imports += 1
            
            except Exception as e:
                results.append(f"❌ Ошибка в строке '{line}': {str(e)}")
                failed_imports += 1
        else:
            results.append(f"❌ Неверный формат строки: '{line}'")
            failed_imports += 1
    
    # Формируем отчет
    report = f"Импорт завершен.\n✅ Успешно: {successful_imports}\n❌ Ошибок: {failed_imports}\n\nРезультаты:\n"
    report += "\n".join(results)
    
    if len(report) > 4096:  # Telegram ограничивает длину сообщения
        # Отправляем результаты частями
        chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
        for i, chunk in enumerate(chunks):
            await update.message.reply_text(f"Часть {i+1}/{len(chunks)}:\n{chunk}")
    else:
        await update.message.reply_text(report)
    
    return ConversationHandler.END

admin_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("admin", admin_entry)],
    states={
        AWAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_admin_password)],
        AWAITING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id)],
        AWAITING_NEW_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_volume)],
    },
    fallbacks=[],
    per_user=True, # Default, but explicit
    per_chat=True  # Add this for better group chat handling
)

change_leaderboard_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("change_leaderboard", change_leaderboard_entry)],
    states={
        AWAITING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id)],
        AWAITING_NEW_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_volume)],
    },
    fallbacks=[],
    per_user=True, # Default, but explicit
    per_chat=True  # Add this for better group chat handling
)

check_submission_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("check_submission", check_submission_entry)],
    states={
        AWAITING_SUBMISSION_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_user_photos)],
        AWAITING_ENTRY_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_entry_action)],
        AWAITING_ACTION_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_or_delete_entry)],
        AWAITING_NEW_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_volume)],
    },
    fallbacks=[],
    per_user=True, # Default, but explicit
    per_chat=True  # Add this for better group chat handling
)

import_users_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("import_users", import_users_entry)],
    states={
        AWAITING_USER_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_list)],
    },
    fallbacks=[],
    per_user=True,
    per_chat=True
)