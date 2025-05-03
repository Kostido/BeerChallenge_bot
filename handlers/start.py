from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
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

    # Define buttons
    keyboard = [
        [KeyboardButton("Выпил пиво"), KeyboardButton("Таблица лидеров")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_html(
        rf"<b>Привет, {user.mention_html()}!</b> 👋"
        f"\n\nТеперь ты участник в <b>Пивном Челлендже 🍻 Летний Кубок 2025</b> 🏆"
        f"\n\n👇 <b>Как участвовать:</b>\n"
        f"1️⃣ Нажми кнопку '<i>Выпил пиво</i>' 🍺\n"
        f"2️⃣ Отправь мне <b>фото с пивом</b> 📸\n"
        f"3️⃣ Укажи <b>объем</b> в литрах (например, 0.5) 💧\n"
        f"\n👀 Жми '<i>Таблица лидеров</i>', чтобы узнать, кто впереди! 🥇🥈🥉\n"
        rf"Удачи и приятного пивопития! 😉",
        reply_markup=reply_markup, # Add the keyboard here
    )