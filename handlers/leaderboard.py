# handlers/leaderboard.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from db_utils import get_db, get_leaderboard

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and displays the current leaderboard from the database."""
    user = update.effective_user
    logger.info(f"User {user.first_name} ({user.id}) requested leaderboard.")

    try:
        with next(get_db()) as db:
            leaderboard_data = get_leaderboard(db, limit=10) # Get top 10

        if not leaderboard_data:
            leaderboard_text = "Таблица лидеров пока пуста. Будь первым! 🍻"
        else:
            leaderboard_text = "🏆 Таблица лидеров Franema Summer Beer Challenge: 🏆\n\n"
            for i, (name, volume) in enumerate(leaderboard_data, start=1):
                # Ensure name is not None before formatting
                display_name = name if name else f"User ID: {update.effective_user.id}" # Fallback if name is None
                leaderboard_text += f"{i}. {display_name} - {volume:.2f} л\n"

        await update.message.reply_text(leaderboard_text)

    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}", exc_info=True)
        await update.message.reply_text("Не удалось загрузить таблицу лидеров. Попробуйте позже.")

# Handler for /leaderboard command
leaderboard_handler = CommandHandler("leaderboard", show_leaderboard)