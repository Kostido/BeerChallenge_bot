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
AWAITING_DELETE_USER_ID, AWAITING_DELETE_CONFIRMATION = range(7, 9)

admin_ids = set()  # Временное хранение id админов

async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите пароль администратора:")
    return AWAITING_PASSWORD

async def check_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == ADMIN_PASSWORD:
        admin_ids.add(update.effective_user.id)
        await update.message.reply_text("Режим администратора активирован.\nДоступные команды:\n/change_leaderboard — изменить объем участника\n/check_submission — посмотреть фото участника\n/delete_user — удалить участника\n/list_users — показать список участников")
        return ConversationHandler.END
    await update.message.reply_text("Неверный пароль. Попробуйте снова или /cancel.")
    return AWAITING_PASSWORD

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий диалог администратора и завершает разговор."""
    user = update.message.from_user
    logger.info(f"Admin {user.first_name} ({user.id}) canceled the conversation via command.")
    
    # Очищаем все временные данные пользователя
    context.user_data.clear()
    
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END

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
        "ID: 123456789, Имя: Имя_участника, Ник: @username, Объем: X.XX л\n"
        "ID: 987654321, Имя: Другой_участник, Ник: нет, Объем: Y.YY л\n\n"
        "Каждый участник должен быть на отдельной строке.\n"
        "Поле 'Ник:' обязательно, если нет ника - укажите 'нет'"
    )
    return AWAITING_USER_LIST

async def receive_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает полученный список пользователей и добавляет их в базу данных."""
    user_list_text = update.message.text
    user_lines = user_list_text.strip().split('\n')
    
    successful_imports = 0
    failed_imports = 0
    results = []
    
    # Регулярное выражение для извлечения данных из строки с поддержкой обоих форматов
    pattern = r'ID:\s*(\d+),\s*Имя:\s*([^,]+),\s*Ник:\s*([^,]+),\s*Объем:\s*(\d+\.?\d*)\s*л'
    
    for line in user_lines:
        match = re.search(pattern, line)
        if match:
            user_id, name, username_raw, volume = match.groups()
            
            try:
                user_id = int(user_id)
                volume = float(volume)
                
                # Обрабатываем username
                username = None
                if username_raw.strip().lower() not in ['нет', 'no', '-', '']:
                    # Убираем @ если есть, и очищаем пробелы
                    username = username_raw.strip().lstrip('@')
                    if username:  # Проверяем что не пустая строка
                        username = username
                    else:
                        username = None
                
                with next(get_db()) as db:
                    # Добавляем или обновляем пользователя
                    add_or_update_user(db, user_id=user_id, first_name=name.strip(), username=username)
                    
                    # Удаляем существующие записи о пиве для этого пользователя
                    db.query(BeerEntry).filter(BeerEntry.user_id == user_id).delete()
                    
                    # Добавляем новую запись с указанным объемом
                    db.add(BeerEntry(user_id=user_id, volume_liters=volume, photo_file_id="imported_by_admin"))
                    db.commit()
                
                # Форматируем результат
                username_display = f"@{username}" if username else "нет"
                results.append(f"✅ ID: {user_id}, Имя: {name.strip()}, Ник: {username_display}, Объем: {volume:.2f} л")
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

async def delete_user_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запускает процесс удаления пользователя."""
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("Нет доступа. Введите /admin для входа.")
        return ConversationHandler.END
    
    # Показываем список всех пользователей
    try:
        with next(get_db()) as db:
            users = db.query(User).all()

        if not users:
            await update.message.reply_text("Список участников пуст.")
            return ConversationHandler.END

        user_list_text = "Список участников для удаления:\n"
        for user in users:
            # Получаем общий объем пива для каждого пользователя
            with next(get_db()) as db:
                total_volume = db.query(BeerEntry).filter(BeerEntry.user_id == user.id).with_entities(func.sum(BeerEntry.volume_liters)).scalar() or 0
            user_list_text += f"ID: {user.id}, Имя: {user.first_name}, Объем: {total_volume:.2f} л\n"

        await update.message.reply_text(user_list_text + "\nВведите ID пользователя для удаления:")
        return AWAITING_DELETE_USER_ID

    except Exception as e:
        logger.error(f"Error fetching users for deletion: {e}", exc_info=True)
        await update.message.reply_text("Не удалось загрузить список участников. Попробуйте позже.")
        return ConversationHandler.END

async def receive_delete_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает ID пользователя для удаления и запрашивает подтверждение."""
    user_id = update.message.text
    
    try:
        user_id = int(user_id)
        
        # Проверяем, существует ли пользователь
        with next(get_db()) as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                await update.message.reply_text("Пользователь с таким ID не найден. Попробуйте еще раз или /cancel для отмены.")
                return AWAITING_DELETE_USER_ID
            
            # Получаем общий объем пива
            total_volume = db.query(BeerEntry).filter(BeerEntry.user_id == user_id).with_entities(func.sum(BeerEntry.volume_liters)).scalar() or 0
            
            # Сохраняем данные пользователя для удаления
            context.user_data['delete_user_id'] = user_id
            context.user_data['delete_user_name'] = user.first_name
            context.user_data['delete_user_volume'] = total_volume
            
            await update.message.reply_text(
                f"❗️ ВНИМАНИЕ ❗️\n\n"
                f"Вы собираетесь удалить участника:\n"
                f"ID: {user_id}\n"
                f"Имя: {user.first_name}\n"
                f"Общий объем: {total_volume:.2f} л\n\n"
                f"Это действие удалит пользователя и ВСЕ его записи о пиве из базы данных!\n"
                f"Это действие НЕОБРАТИМО!\n\n"
                f"Введите 'УДАЛИТЬ' (заглавными буквами) для подтверждения или /cancel для отмены:"
            )
            return AWAITING_DELETE_CONFIRMATION
            
    except ValueError:
        await update.message.reply_text("Неверный формат ID. Введите числовой ID или /cancel для отмены.")
        return AWAITING_DELETE_USER_ID
    except Exception as e:
        logger.error(f"Error checking user for deletion: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при проверке пользователя. Попробуйте позже.")
        return ConversationHandler.END

async def confirm_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Подтверждает и выполняет удаление пользователя."""
    confirmation = update.message.text.strip()
    
    if confirmation != "УДАЛИТЬ":
        await update.message.reply_text("Удаление отменено. Для подтверждения нужно ввести 'УДАЛИТЬ' заглавными буквами.")
        return ConversationHandler.END
    
    # Получаем данные пользователя из контекста
    user_id = context.user_data.get('delete_user_id')
    user_name = context.user_data.get('delete_user_name')
    user_volume = context.user_data.get('delete_user_volume')
    
    if not user_id:
        await update.message.reply_text("Ошибка: данные пользователя не найдены. Попробуйте снова.")
        return ConversationHandler.END
    
    try:
        with next(get_db()) as db:
            # Удаляем все записи о пиве пользователя
            deleted_entries = db.query(BeerEntry).filter(BeerEntry.user_id == user_id).delete()
            
            # Удаляем самого пользователя
            deleted_user = db.query(User).filter(User.id == user_id).delete()
            
            # Применяем изменения
            db.commit()
            
            if deleted_user > 0:
                await update.message.reply_text(
                    f"✅ Участник успешно удален:\n"
                    f"ID: {user_id}\n"
                    f"Имя: {user_name}\n"
                    f"Удалено записей о пиве: {deleted_entries}\n"
                    f"Удаленный объем: {user_volume:.2f} л"
                )
                logger.info(f"Admin {update.effective_user.id} deleted user {user_id} ({user_name}) with {deleted_entries} beer entries")
            else:
                await update.message.reply_text("Пользователь не был найден (возможно, уже удален).")
                
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при удалении пользователя. Попробуйте позже.")
    
    # Очищаем временные данные
    context.user_data.pop('delete_user_id', None)
    context.user_data.pop('delete_user_name', None)
    context.user_data.pop('delete_user_volume', None)
    
    return ConversationHandler.END

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает простой список всех участников с их данными."""
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text("Нет доступа. Введите /admin для входа.")
        return
    
    try:
        with next(get_db()) as db:
            users = db.query(User).all()

        if not users:
            await update.message.reply_text("Список участников пуст.")
            return

        user_list_text = "Список участников:\n"
        for user in users:
            # Получаем общий объем пива для каждого пользователя
            with next(get_db()) as db:
                total_volume = db.query(BeerEntry).filter(BeerEntry.user_id == user.id).with_entities(func.sum(BeerEntry.volume_liters)).scalar() or 0
            
            # Форматируем строку с учетом наличия username
            if user.username:
                user_list_text += f"ID: {user.id}, Имя: {user.first_name}, Ник: @{user.username}, Объем: {total_volume:.2f} л\n"
            else:
                user_list_text += f"ID: {user.id}, Имя: {user.first_name}, Ник: нет, Объем: {total_volume:.2f} л\n"

        # Разбиваем на части если текст слишком длинный для Telegram
        if len(user_list_text) > 4096:
            chunks = [user_list_text[i:i+4000] for i in range(0, len(user_list_text), 4000)]
            for i, chunk in enumerate(chunks):
                await update.message.reply_text(f"Часть {i+1}/{len(chunks)}:\n{chunk}")
        else:
            await update.message.reply_text(user_list_text)

    except Exception as e:
        logger.error(f"Error fetching users list: {e}", exc_info=True)
        await update.message.reply_text("Не удалось загрузить список участников. Попробуйте позже.")

admin_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("admin", admin_entry)],
    states={
        AWAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_admin_password)],
        AWAITING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id)],
        AWAITING_NEW_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_volume)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_user=True, # Default, but explicit
    per_chat=True  # Add this for better group chat handling
)

change_leaderboard_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("change_leaderboard", change_leaderboard_entry)],
    states={
        AWAITING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id)],
        AWAITING_NEW_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_volume)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
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
    fallbacks=[CommandHandler('cancel', cancel)],
    per_user=True, # Default, but explicit
    per_chat=True  # Add this for better group chat handling
)

import_users_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("import_users", import_users_entry)],
    states={
        AWAITING_USER_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_list)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_user=True,
    per_chat=True
)

delete_user_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("delete_user", delete_user_entry)],
    states={
        AWAITING_DELETE_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_delete_user_id)],
        AWAITING_DELETE_CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_user)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_user=True,
    per_chat=True
)