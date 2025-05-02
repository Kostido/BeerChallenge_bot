from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from db_utils import add_or_update_user, get_db
from models import User # Import User if needed, or rely on db_utils

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot and registers/updates the user."""
    user = update.effective_user
    if not user:
        # Handle cases where user is None, though unlikely for a command
        return

    # Add or update user in the database
    with next(get_db()) as db:
        add_or_update_user(db, user_id=user.id, first_name=user.first_name, username=user.username)
    await update.message.reply_html(
        rf"Привет, {user.mention_html()}!"
        f"\n\nЯ бот для пивного челленджа Franema Summer Beer Challenge!"
        f"\n\nОтправь мне фото с пивом и укажи объем в литрах, чтобы засчитать его."
        f"\nИспользуй /leaderboard, чтобы увидеть таблицу лидеров."
        f"\nУдачи!",
    )