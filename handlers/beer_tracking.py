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
    
    # Сохраняем ID и chat_id сообщения с фотографией для последующего удаления
    context.user_data['original_message_id'] = message.message_id
    context.user_data['original_chat_id'] = message.chat_id
    logger.info(f"Stored original message details: message_id={message.message_id}, chat_id={message.chat_id}")

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
        
        # Удаляем сообщение-подсказку при отмене
        prompt_message_id = context.user_data.get('prompt_message_id')
        prompt_chat_id = context.user_data.get('prompt_chat_id')
        
        if prompt_message_id and prompt_chat_id:
            try:
                await context.bot.delete_message(
                    chat_id=prompt_chat_id,
                    message_id=prompt_message_id
                )
                logger.info(f"Deleted prompt message after cancel: {prompt_message_id}")
            except Exception as delete_error:
                logger.error(f"Failed to delete prompt message after cancel: {delete_error}", exc_info=True)
        
        # Очищаем user_data
        if 'photo_file_id' in context.user_data:
            del context.user_data['photo_file_id']
        if 'original_message_id' in context.user_data:
            del context.user_data['original_message_id']
        if 'original_chat_id' in context.user_data:
            del context.user_data['original_chat_id']
        if 'prompt_message_id' in context.user_data:
            del context.user_data['prompt_message_id']
        if 'prompt_chat_id' in context.user_data:
            del context.user_data['prompt_chat_id']
            
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
            logger.info(f"User {user.id} old volume: {old_volume} L")
            
            db_user = add_or_update_user(db, user_id=user.id, first_name=user.first_name, username=user.username)
            add_beer_entry(db, user_id=db_user.id, volume=volume, photo_id=photo_file_id)
            
            # Получаем обновленный объем после добавления
            new_volume = get_user_total_volume(db, user.id)
            logger.info(f"User {user.id} new volume: {new_volume} L")

        # Сообщение пользователю в личный чат
        await query.edit_message_text(
            text=f"Отлично! Засчитано {volume:.2f} л пива. 🍻\nВсего ты выпил(а): {new_volume:.2f} л пива."
        )
        
        # Отправляем фото и информацию в групповой чат
        if GROUP_CHAT_ID:
            username = f"@{user.username}" if user.username else user.first_name
            caption = f"🍺 {username} выпил(а) {volume:.2f} л пива! 🍻\n📊 Всего выпито: {new_volume:.2f} л"
            try:
                # Получаем сохраненные данные об исходном сообщении с фотографией
                original_message_id = context.user_data.get('original_message_id')
                original_chat_id = context.user_data.get('original_chat_id')

                # Отправляем фото от имени бота
                await context.bot.send_photo(
                    chat_id=GROUP_CHAT_ID,
                    photo=photo_file_id,
                    caption=caption
                )
                logger.info(f"Beer submission forwarded to group chat: {GROUP_CHAT_ID}")
                
                # Удаляем исходное сообщение пользователя с фотографией,
                # если находимся в групповом чате и удалось получить ID исходного сообщения
                if original_message_id and original_chat_id == GROUP_CHAT_ID:
                    try:
                        await context.bot.delete_message(
                            chat_id=original_chat_id,
                            message_id=original_message_id
                        )
                        logger.info(f"Original user photo message deleted: {original_message_id}")
                    except Exception as delete_error:
                        logger.error(f"Failed to delete original message: {delete_error}", exc_info=True)
                
                # Удаляем сообщение с инлайн-клавиатурой в групповом чате
                if query.message.chat_id == GROUP_CHAT_ID:
                    try:
                        await context.bot.delete_message(
                            chat_id=query.message.chat_id,
                            message_id=query.message.message_id
                        )
                        logger.info(f"Inline keyboard message deleted in group chat: {query.message.message_id}")
                    except Exception as delete_error:
                        logger.error(f"Failed to delete inline keyboard message: {delete_error}", exc_info=True)
            except Exception as e:
                logger.error(f"Failed to forward submission to group chat: {e}", exc_info=True)
        else:
            logger.warning("GROUP_CHAT_ID not set, cannot forward beer submission")
        
        # Проверяем достижения пользователя
        logger.debug(f"Checking achievements for user {user.id}: old={old_volume}, new={new_volume}")
        new_achievement = check_new_achievement(old_volume, new_volume)
        
        if new_achievement:
            logger.info(f"User {user.id} reached new achievement: {new_achievement['title']} ({new_achievement['volume']} L)")
            username_display = f"@{user.username}" if user.username else user.first_name
            achievement_message = format_achievement_message(new_achievement, username_display)
            
            # Отладка путей к изображениям
            image_path = new_achievement.get('image', '')
            logger.debug(f"Achievement image path: {image_path}")
            logger.debug(f"Image exists: {os.path.exists(image_path) if image_path else 'N/A'}")
            logger.debug(f"Current directory: {os.getcwd()}")
            
            # Отправляем сообщение и изображение о достижении только в групповой чат
            if GROUP_CHAT_ID:
                try:
                    logger.info(f"Trying to send achievement notification to group chat: {GROUP_CHAT_ID}")
                    # Проверяем, существует ли файл изображения
                    if image_path and os.path.exists(image_path):
                        logger.info(f"Sending achievement with image: {image_path}")
                        with open(image_path, 'rb') as photo:
                            await context.bot.send_photo(
                                chat_id=GROUP_CHAT_ID,
                                photo=photo,
                                caption=achievement_message
                            )
                    else:
                        logger.warning(f"Achievement image not found: {image_path}, sending text only")
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
                        logger.info("Trying to send fallback text-only achievement notification")
                        await context.bot.send_message(
                            chat_id=GROUP_CHAT_ID,
                            text=achievement_message
                        )
                        logger.info("Fallback text-only achievement notification sent")
                    except Exception as inner_e:
                        logger.error(f"Also failed to send text-only achievement: {inner_e}", exc_info=True)
            else:
                logger.warning("GROUP_CHAT_ID not set, cannot send achievement notification")
        else:
            logger.debug(f"No new achievement for user {user.id}")
        
        logger.info(f"Successfully added entry for user {user.id}: {volume}L")
        
        # Удаляем сообщение-подсказку "Отправь мне фото с пивом", если оно было сохранено
        prompt_message_id = context.user_data.get('prompt_message_id')
        prompt_chat_id = context.user_data.get('prompt_chat_id')
        
        if prompt_message_id and prompt_chat_id:
            try:
                await context.bot.delete_message(
                    chat_id=prompt_chat_id,
                    message_id=prompt_message_id
                )
                logger.info(f"Deleted prompt message: {prompt_message_id} in chat {prompt_chat_id}")
                
                # Очищаем данные о сообщении
                del context.user_data['prompt_message_id']
                del context.user_data['prompt_chat_id']
            except Exception as delete_error:
                logger.error(f"Failed to delete prompt message: {delete_error}", exc_info=True)
        
        # Clear stored data
        if 'photo_file_id' in context.user_data:
            del context.user_data['photo_file_id']
        if 'original_message_id' in context.user_data:
            del context.user_data['original_message_id']
        if 'original_chat_id' in context.user_data:
            del context.user_data['original_chat_id']
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Database error while adding beer entry for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(text="Произошла ошибка при сохранении данных. Попробуй позже.")
        
        # Удаляем сообщение-подсказку при ошибке
        prompt_message_id = context.user_data.get('prompt_message_id')
        prompt_chat_id = context.user_data.get('prompt_chat_id')
        
        if prompt_message_id and prompt_chat_id:
            try:
                await context.bot.delete_message(
                    chat_id=prompt_chat_id,
                    message_id=prompt_message_id
                )
                logger.info(f"Deleted prompt message after error: {prompt_message_id}")
            except Exception as delete_error:
                logger.error(f"Failed to delete prompt message after error: {delete_error}", exc_info=True)
        
        # Clear stored data even on error
        if 'photo_file_id' in context.user_data:
             del context.user_data['photo_file_id']
        if 'original_message_id' in context.user_data:
            del context.user_data['original_message_id']
        if 'original_chat_id' in context.user_data:
            del context.user_data['original_chat_id']
        if 'prompt_message_id' in context.user_data:
            del context.user_data['prompt_message_id']
        if 'prompt_chat_id' in context.user_data:
            del context.user_data['prompt_chat_id']
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation (used by /cancel command)."""
    user = update.message.from_user
    logger.info(f"User {user.first_name} ({user.id}) canceled the conversation via command.")
    
    # Удаляем сообщение-подсказку при отмене через команду
    prompt_message_id = context.user_data.get('prompt_message_id')
    prompt_chat_id = context.user_data.get('prompt_chat_id')
    
    if prompt_message_id and prompt_chat_id:
        try:
            await context.bot.delete_message(
                chat_id=prompt_chat_id,
                message_id=prompt_message_id
            )
            logger.info(f"Deleted prompt message after cancel command: {prompt_message_id}")
        except Exception as delete_error:
            logger.error(f"Failed to delete prompt message after cancel command: {delete_error}", exc_info=True)
    
    # Clear stored data if any
    if 'photo_file_id' in context.user_data:
        del context.user_data['photo_file_id']
    if 'original_message_id' in context.user_data:
        del context.user_data['original_message_id']
    if 'original_chat_id' in context.user_data:
        del context.user_data['original_chat_id']
    if 'prompt_message_id' in context.user_data:
        del context.user_data['prompt_message_id']
    if 'prompt_chat_id' in context.user_data:
        del context.user_data['prompt_chat_id']

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