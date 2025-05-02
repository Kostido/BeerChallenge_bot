# handlers/beer_tracking.py
import logging
from telegram import Update, Message, PhotoSize
from telegram import Update, Message, PhotoSize
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
    CommandHandler,
)
from db_utils import add_or_update_user, add_beer_entry, get_db

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
AWAITING_VOLUME = 1

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles incoming photos, stores file_id, and asks for volume."""
    message: Message | None = update.message
    user = message.from_user
    photo: tuple[PhotoSize, ...] | None = message.photo

    if not photo:
        logger.warning("Received message with photo filter but no photo.")
        return

    # For simplicity, let's just acknowledge the photo for now.
    # We'll add database interaction and volume request later.
    photo_file_id = photo[-1].file_id # Get the highest resolution photo
    logger.info(f"Received photo from {user.first_name} ({user.id}). File ID: {photo_file_id}")

    # Store photo file_id for the next step
    context.user_data['photo_file_id'] = photo_file_id

    await message.reply_text(
        "Фото получил! 👍 Теперь укажи объем выпитого пива в литрах (например, '0.5' или '1')."
        "\nИли отправь /cancel для отмены."
    )

    return AWAITING_VOLUME # Transition to the next state

async def handle_volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the volume input, saves the entry, and ends the conversation."""
    message: Message | None = update.message
    user = message.from_user
    volume_text = message.text
    photo_file_id = context.user_data.get('photo_file_id')

    if not user or not photo_file_id:
        logger.warning("User or photo_file_id missing in handle_volume.")
        await message.reply_text("Что-то пошло не так. Попробуй отправить фото еще раз.")
        return ConversationHandler.END

    try:
        volume = float(volume_text.replace(',', '.')) # Allow comma as decimal separator
        if volume <= 0:
            raise ValueError("Volume must be positive.")
    except ValueError:
        await message.reply_text(
            "Неверный формат объема. Пожалуйста, введи число (например, 0.5 или 1)."
            "\nИли отправь /cancel для отмены."
        )
        return AWAITING_VOLUME # Stay in the same state

    # Save to database
    try:
        with next(get_db()) as db:
            # Ensure user exists
            db_user = add_or_update_user(db, user_id=user.id, first_name=user.first_name, username=user.username)
            # Add beer entry
            add_beer_entry(db, user_id=db_user.id, volume=volume, photo_id=photo_file_id)

        await message.reply_text(
            f"Отлично! Засчитано {volume:.2f} л пива. 🍻"
        )
        logger.info(f"Successfully added entry for user {user.id}: {volume}L")
        # Clear stored data
        del context.user_data['photo_file_id']
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Database error while adding beer entry for user {user.id}: {e}", exc_info=True)
        await message.reply_text("Произошла ошибка при сохранении данных. Попробуй позже.")
        # Clear stored data even on error
        if 'photo_file_id' in context.user_data:
             del context.user_data['photo_file_id']
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info(f"User {user.first_name} ({user.id}) canceled the conversation.")
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
        AWAITING_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_volume)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)