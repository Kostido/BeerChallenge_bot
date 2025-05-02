import logging
import os

from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv

from config import BOT_TOKEN
from handlers.start import start
# Use the conversation handler for beer tracking
from handlers.beer_tracking import beer_tracking_conv_handler 
from database.database import init_db # Import table creation function from database module
from handlers.leaderboard import leaderboard_handler
from handlers.admin import admin_conv_handler, change_leaderboard_conv_handler, check_submission_conv_handler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


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
    application.add_handler(beer_tracking_conv_handler) # Add the conversation handler
    application.add_handler(leaderboard_handler)
    application.add_handler(admin_conv_handler)
    application.add_handler(change_leaderboard_conv_handler)
    application.add_handler(check_submission_conv_handler)

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == "__main__":
    main()