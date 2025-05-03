# handlers/leaderboard.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.error import BadRequest # Import BadRequest
from db_utils import get_db, get_leaderboard

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
            leaderboard_data = get_leaderboard(db, limit=10) # Get top 10

        if not leaderboard_data:
            leaderboard_text = "Таблица лидеров пока пуста. Будь первым! 🍻"
        else:
            leaderboard_text = "🏆 Таблица лидеров Franema Summer Beer Challenge: 🏆\n\n"
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
                leaderboard_text += f"{medal} {display_name} - {volume:.2f} л\n"

        sent_message = await update.message.reply_text(leaderboard_text)

        # Store the new message ID per user
        context.user_data[f'last_leaderboard_message_id_{user_id}'] = sent_message.message_id
        # Update the last request time for the user
        context.user_data[f'leaderboard_last_request_{user_id}'] = current_time
        logger.info(f"Stored new leaderboard message ID {sent_message.message_id} for user {user_id} in chat {chat_id}.")

    except Exception as e:
        logger.error(f"Error fetching or sending leaderboard for user {user_id} in chat {chat_id}: {e}", exc_info=True)
        await update.message.reply_text("Не удалось загрузить таблицу лидеров. Попробуйте позже.")

# Handler for /leaderboard command (or button press)
# Note: The handler registration is in main.py using MessageHandler
# leaderboard_handler = CommandHandler("leaderboard", show_leaderboard) # Keep this if you also want /leaderboard command