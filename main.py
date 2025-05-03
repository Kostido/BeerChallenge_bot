import logging
import os

from telegram import Update # Added import
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes # Added ContextTypes
from dotenv import load_dotenv

from config import BOT_TOKEN
from handlers.start import start
# Use the conversation handler for beer tracking
from handlers.beer_tracking import beer_tracking_conv_handler, AWAITING_VOLUME_CHOICE # Import state
from handlers.leaderboard import show_leaderboard # Import the function directly 
from database.database import init_db # Import table creation function from database module
# leaderboard_handler is now handled by MessageHandler below
from handlers.admin import admin_conv_handler, change_leaderboard_conv_handler, check_submission_conv_handler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def prompt_for_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompts the user to send a photo when the 'Выпил пиво' button is pressed."""
    await update.message.reply_text(
        "Отлично! Теперь отправь мне фото с пивом, чтобы я мог его засчитать. 📸"
        "\nИли отправь /cancel, если передумал."
    )
    # Note: We don't return a state here, as the photo handler will trigger the conversation.


def main() -> None:
    """Start the bot."""
    # Load environment variables from .env file
    load_dotenv()

    # Create database tables if they don't exist
    logger.info("Creating database tables if they don't exist...")
    init_db()
    logger.info("Database tables checked/created.")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # Add handlers for the buttons
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^Выпил пиво$'), prompt_for_photo))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^Таблица лидеров$'), show_leaderboard))

    # Add the conversation handler for beer tracking (starts with photo)
    application.add_handler(beer_tracking_conv_handler)
    application.add_handler(admin_conv_handler)
    application.add_handler(change_leaderboard_conv_handler)
    application.add_handler(check_submission_conv_handler)

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == "__main__":
    main()