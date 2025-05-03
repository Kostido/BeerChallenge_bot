from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, CommandHandler
from db_utils import add_or_update_user, add_beer_entry, get_db, get_user_total_volume
from models import User # Import User if needed, or rely on db_utils
import logging

# Enable logging
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot and registers/updates the user."""
    user = update.effective_user
    if not user:
        # Handle cases where user is None, though unlikely for a command
        return

    # Add or update user in the database
    with next(get_db()) as db:
        db_user = add_or_update_user(db, user_id=user.id, first_name=user.first_name, username=user.username)
        
        # Проверяем, есть ли у пользователя записи о пиве
        total_volume = get_user_total_volume(db, user.id)
        
        # Если у пользователя нет записей (новый пользователь), 
        # добавляем начальную запись с объемом 0.0 литров
        if total_volume == 0.0:
            try:
                # Используем пустую строку для photo_id, так как нет реальной фотографии
                add_beer_entry(db, user_id=db_user.id, volume=0.0, photo_id="initial_zero_volume")
                logger.info(f"Added initial zero volume entry for user {user.id}")
            except Exception as e:
                logger.error(f"Error adding initial zero volume entry: {e}", exc_info=True)

    # Define buttons
    keyboard = [
        [KeyboardButton("Выпил пиво"), KeyboardButton("Таблица лидеров")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_html(
        rf"<b>Привет, {user.mention_html()}!</b> 👋"
        f"\n\nТеперь ты участник в <b>Пивном Челлендже 🍻 Летний Кубок 2025</b> 🏆",
        reply_markup=reply_markup, # Add the keyboard here
    )

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends information about how to participate in the beer challenge."""
    await update.message.reply_html(
        f"<b>Как участвовать в Пивном Челлендже:</b>\n\n"
        f"1️⃣ Отправь мне фото с пивом 📸 (без пива - будет анулировано)\n"
        f"2️⃣ Укажи объем в литрах (например, 0.5) 💧\n\n"
        f"👀 Жми /leaderboard чтобы узнать, кто впереди! 🥇🥈\n"
        f"Удачи и приятного пивопития! 😉"
    )

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the rules of the beer challenge."""
    await update.message.reply_html(
        f"<b>📜 ПРАВИЛА ПИВНОГО ЧЕЛЛЕНДЖА 📜</b>\n\n"
        f"🗓 Конкурс длится до <b>31 августа 2025 года</b> включительно\n\n"
        f"🍺 Присылать нужно <b>фото с пивом в руке</b> (сидр считается). Без пива будет анулироваться модератором\n\n"
        f"🥃 Другой алкоголь в данном соревновании <b>не участвует</b> (прости Гор)\n\n"
        f"🏅 После прохождения определенных рубежей выпитого объема пива, вас будут <b>награждать званиями</b>!\n\n"
        f"⚖️ <b>Большая просьба не мухливать и не обманывать</b>\n\n"
        f"💪 <i>Победит сильнейший! Да прибудет с вами сила!</i> 🏆"
    )