# handlers/beer_tracking.py
import logging
import os
from typing import Optional, List, Tuple
from telegram import Update, Message, PhotoSize, InlineKeyboardButton, InlineKeyboardMarkup # Added InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler, # Added CallbackQueryHandler
)
from db_utils import add_or_update_user, add_beer_entry, get_db, get_user_total_volume
from config import GROUP_CHAT_ID  # Импортируем ID группового чата
from handlers.achievements import check_new_achievement, format_achievement_message

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
AWAITING_VOLUME_CHOICE = 1 # Renamed state

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles incoming photos, stores file_id, and asks for volume via buttons."""
    message: Optional[Message] = update.message
    user = message.from_user
    photo: Optional[Tuple[PhotoSize, ...]] = message.photo

    if not photo:
        logger.warning("Received message with photo filter but no photo.")
        # Decide how to handle this - maybe end conversation or ask again?
        return ConversationHandler.END # Or another appropriate state/action

    photo_file_id = photo[-1].file_id # Get the highest resolution photo
    logger.info(f"Received photo from {user.first_name} ({user.id}). File ID: {photo_file_id}")

    # Store photo file_id for the next step
    context.user_data['photo_file_id'] = photo_file_id

    # Define the volume options
    keyboard = [
        [InlineKeyboardButton("0.3 л", callback_data='0.3'), InlineKeyboardButton("0.4 л", callback_data='0.4')],
        [InlineKeyboardButton("0.5 л", callback_data='0.5'), InlineKeyboardButton("1.0 л", callback_data='1.0')],
        [InlineKeyboardButton("1.5 л", callback_data='1.5'), InlineKeyboardButton("2.0 л", callback_data='2.0')],
        [InlineKeyboardButton("Отмена", callback_data='cancel_volume')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_text(
        "Фото получил! 👍 Теперь выбери объем выпитого пива:",
        reply_markup=reply_markup
    )

    return AWAITING_VOLUME_CHOICE # Transition to the state waiting for button press

async def handle_volume_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the volume button press, saves the entry, and ends the conversation."""
    query = update.callback_query
    await query.answer() # Answer the callback query first

    user = query.from_user
    volume_data = query.data
    photo_file_id = context.user_data.get('photo_file_id')

    if volume_data == 'cancel_volume':
        logger.info(f"User {user.first_name} ({user.id}) canceled volume selection.")
        if 'photo_file_id' in context.user_data:
            del context.user_data['photo_file_id']
        await query.edit_message_text(text="Добавление пива отменено.")
        return ConversationHandler.END

    if not user or not photo_file_id:
        logger.warning("User or photo_file_id missing in handle_volume_choice.")
        await query.edit_message_text(text="Что-то пошло не так. Попробуй отправить фото еще раз.")
        # Clear data if something is wrong
        if 'photo_file_id' in context.user_data:
            del context.user_data['photo_file_id']
        return ConversationHandler.END

    try:
        volume = float(volume_data)
    except ValueError:
        logger.error(f"Invalid volume data received from callback: {volume_data}")
        await query.edit_message_text(text="Произошла внутренняя ошибка. Попробуйте позже.")
        if 'photo_file_id' in context.user_data:
            del context.user_data['photo_file_id']
        return ConversationHandler.END

    # Save to database
    try:
        with next(get_db()) as db:
            # Получаем текущий объем выпитого пива перед добавлением новой записи
            old_volume = get_user_total_volume(db, user.id)
            
            db_user = add_or_update_user(db, user_id=user.id, first_name=user.first_name, username=user.username)
            add_beer_entry(db, user_id=db_user.id, volume=volume, photo_id=photo_file_id)
            
            # Получаем обновленный объем после добавления
            new_volume = get_user_total_volume(db, user.id)

        # Сообщение пользователю
        await query.edit_message_text(
            text=f"Отлично! Засчитано {volume:.2f} л пива. 🍻"
        )
        
        # Отправляем фото и информацию в групповой чат
        if GROUP_CHAT_ID:
            username = f"@{user.username}" if user.username else user.first_name
            caption = f"🍺 {username} выпил(а) {volume:.2f} л пива! 🍻"
            try:
                await context.bot.send_photo(
                    chat_id=GROUP_CHAT_ID,
                    photo=photo_file_id,
                    caption=caption
                )
                logger.info(f"Beer submission forwarded to group chat: {GROUP_CHAT_ID}")
            except Exception as e:
                logger.error(f"Failed to forward submission to group chat: {e}", exc_info=True)
        else:
            logger.warning("GROUP_CHAT_ID not set, cannot forward beer submission")
        
        # Проверяем достижения пользователя
        new_achievement = check_new_achievement(old_volume, new_volume)
        if new_achievement:
            username_display = f"@{user.username}" if user.username else user.first_name
            achievement_message = format_achievement_message(new_achievement, username_display)
            
            # Отправляем сообщение и изображение о достижении пользователю
            try:
                # Проверяем, существует ли файл изображения
                if os.path.exists(new_achievement['image']):
                    with open(new_achievement['image'], 'rb') as photo:
                        await context.bot.send_photo(
                            chat_id=user.id,
                            photo=photo,
                            caption=achievement_message
                        )
                else:
                    # Если файл не существует, отправляем только текстовое сообщение
                    await context.bot.send_message(
                        chat_id=user.id,
                        text=achievement_message
                    )
                    logger.warning(f"Achievement image not found: {new_achievement['image']}")
            except Exception as e:
                logger.error(f"Failed to send achievement to user: {e}", exc_info=True)
                # Если не удалось отправить изображение, отправляем только текст
                await context.bot.send_message(
                    chat_id=user.id,
                    text=achievement_message
                )
            
            # Отправляем сообщение и изображение о достижении в групповой чат
            if GROUP_CHAT_ID:
                try:
                    # Проверяем, существует ли файл изображения
                    if os.path.exists(new_achievement['image']):
                        with open(new_achievement['image'], 'rb') as photo:
                            await context.bot.send_photo(
                                chat_id=GROUP_CHAT_ID,
                                photo=photo,
                                caption=achievement_message
                            )
                    else:
                        # Если файл не существует, отправляем только текстовое сообщение
                        await context.bot.send_message(
                            chat_id=GROUP_CHAT_ID,
                            text=achievement_message
                        )
                    logger.info(f"Achievement notification sent to group chat: {GROUP_CHAT_ID}")
                except Exception as e:
                    logger.error(f"Failed to send achievement notification to group chat: {e}", exc_info=True)
                    # Если не удалось отправить изображение, отправляем только текст
                    try:
                        await context.bot.send_message(
                            chat_id=GROUP_CHAT_ID,
                            text=achievement_message
                        )
                    except:
                        pass
        
        logger.info(f"Successfully added entry for user {user.id}: {volume}L")
        # Clear stored data
        del context.user_data['photo_file_id']
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Database error while adding beer entry for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(text="Произошла ошибка при сохранении данных. Попробуй позже.")
        # Clear stored data even on error
        if 'photo_file_id' in context.user_data:
             del context.user_data['photo_file_id']
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation (used by /cancel command)."""
    user = update.message.from_user
    logger.info(f"User {user.first_name} ({user.id}) canceled the conversation via command.")
    # Clear stored data if any
    if 'photo_file_id' in context.user_data:
        del context.user_data['photo_file_id']

    await update.message.reply_text(
        'Добавление пива отменено.'
    )
    return ConversationHandler.END

# Conversation handler for beer tracking
beer_tracking_conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo)],
    states={
        AWAITING_VOLUME_CHOICE: [CallbackQueryHandler(handle_volume_choice)], # Use CallbackQueryHandler
    },
    fallbacks=[CommandHandler('cancel', cancel), CallbackQueryHandler(handle_volume_choice, pattern='^cancel_volume$')], # Also handle cancel button
    per_user=True, # Default, but explicit
    per_chat=True  # Add this for better group chat handling
)