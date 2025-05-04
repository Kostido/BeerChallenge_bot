# handlers/leaderboard.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.error import BadRequest # Import BadRequest
from db_utils import get_db, get_leaderboard
from handlers.achievements import get_achievement_for_volume  # Импортируем функцию для определения званий

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

import time # Import time module

# Cooldown period in seconds
LEADERBOARD_COOLDOWN = 5

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and displays the current leaderboard, deleting the previous one sent by the same user."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_id = user.id
    current_time = time.time()

    # Сохраняем ID сообщения пользователя, запросившего таблицу лидеров, чтобы удалить его позже
    user_message_id = update.message.message_id if update.message else None
    
    # Check cooldown for the user
    last_request_time = context.user_data.get(f'leaderboard_last_request_{user_id}', 0)
    if current_time - last_request_time < LEADERBOARD_COOLDOWN:
        logger.info(f"User {user.first_name} ({user_id}) requested leaderboard too soon in chat {chat_id}. Ignoring.")
        # Optionally send a message to the user
        # await update.message.reply_text("Пожалуйста, подождите немного перед следующим запросом таблицы.", quote=True)
        return # Exit if within cooldown

    logger.info(f"User {user.first_name} ({user_id}) requested leaderboard in chat {chat_id}.")

    # Try to delete the previous leaderboard message sent by this user
    last_message_id = context.user_data.get(f'last_leaderboard_message_id_{user_id}')
    if last_message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_message_id)
            logger.info(f"Deleted previous leaderboard message {last_message_id} for user {user_id} in chat {chat_id}.")
            # Clear the stored ID after successful deletion
            del context.user_data[f'last_leaderboard_message_id_{user_id}']
        except BadRequest as e:
            # Message might have been deleted already or is too old
            logger.warning(f"Could not delete message {last_message_id} for user {user_id} in chat {chat_id}: {e}")
            # Clear the stored ID even if deletion failed to prevent repeated attempts
            if f'last_leaderboard_message_id_{user_id}' in context.user_data:
                 del context.user_data[f'last_leaderboard_message_id_{user_id}']
        except Exception as e:
            logger.error(f"Unexpected error deleting message {last_message_id} for user {user_id} in chat {chat_id}: {e}", exc_info=True)
            # Clear the stored ID even on unexpected errors
            if f'last_leaderboard_message_id_{user_id}' in context.user_data:
                 del context.user_data[f'last_leaderboard_message_id_{user_id}']

    try:
        with next(get_db()) as db:
            leaderboard_data = get_leaderboard(db, limit=100) # Увеличиваем лимит до 100 участников

        if not leaderboard_data:
            leaderboard_text = "Таблица лидеров пока пуста. Будь первым! 🍻"
        else:
            leaderboard_text = "🏆 Таблица лидеров участников - Летний пивной кубок 2025 🏆\n\n"
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for i, (first_name, username, volume) in enumerate(leaderboard_data, start=1):
                # Construct display name with username if available
                display_name_parts = []
                if first_name:
                    display_name_parts.append(first_name)
                if username:
                    display_name_parts.append(f"(@{username})")
                
                if not display_name_parts: # Fallback if both are None/empty
                    # We need the user_id here, but it's not directly available from get_leaderboard
                    # For now, use a generic placeholder. A better solution might involve returning user_id too.
                    display_name = "Участник"
                else:
                    display_name = " ".join(display_name_parts)

                medal = medals.get(i, f"{i}.") # Get medal or use number
                
                # Определяем звание пользователя по объему выпитого пива
                achievement = get_achievement_for_volume(volume)
                achievement_text = f" - {achievement['title']} {achievement['icon']}" if achievement else ""
                
                leaderboard_text += f"{medal} {display_name} - {volume:.2f} л{achievement_text}\n"

        # Отправляем таблицу как новое сообщение (не как reply)
        sent_message = await context.bot.send_message(
            chat_id=chat_id,
            text=leaderboard_text
        )

        # Store the new message ID per user
        context.user_data[f'last_leaderboard_message_id_{user_id}'] = sent_message.message_id
        # Update the last request time for the user
        context.user_data[f'leaderboard_last_request_{user_id}'] = current_time
        logger.info(f"Stored new leaderboard message ID {sent_message.message_id} for user {user_id} in chat {chat_id}.")
        
        # Удаляем сообщение пользователя с запросом таблицы лидеров
        if user_message_id:
            try:
                # Проверяем, является ли чат групповым
                is_group = update.effective_chat.type in ["group", "supergroup"]
                
                if is_group:
                    # Проверяем права бота перед удалением
                    bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
                    can_delete = bot_member.can_delete_messages
                    
                    if can_delete:
                        await context.bot.delete_message(chat_id=chat_id, message_id=user_message_id)
                        logger.info(f"Deleted user's leaderboard request message {user_message_id} in group chat {chat_id}.")
                    else:
                        logger.warning(f"Bot doesn't have delete permissions in group {chat_id}")
                else:
                    # Личная переписка - есть права на удаление
                    await context.bot.delete_message(chat_id=chat_id, message_id=user_message_id)
                    logger.info(f"Deleted user's leaderboard request message {user_message_id} in private chat {chat_id}.")
            except BadRequest as e:
                logger.warning(f"Could not delete user message {user_message_id} in chat {chat_id}: {e}")
            except Exception as e:
                logger.error(f"Error deleting user's leaderboard request: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error fetching or sending leaderboard for user {user_id} in chat {chat_id}: {e}", exc_info=True)
        await update.message.reply_text("Не удалось загрузить таблицу лидеров. Попробуйте позже.")

# Handler for /leaderboard command (or button press)
# Note: The handler registration is in main.py using MessageHandler
# leaderboard_handler = CommandHandler("leaderboard", show_leaderboard) # Keep this if you also want /leaderboard command