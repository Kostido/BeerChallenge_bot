import logging
import os
import datetime
import pytz

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup # Добавлен импорт InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler # Добавлен импорт CallbackQueryHandler
from dotenv import load_dotenv

from config import BOT_TOKEN, GROUP_CHAT_ID # Добавлен импорт GROUP_CHAT_ID
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
    # Отправляем сообщение и сохраняем его
    prompt_message = await update.message.reply_text(
        "Отлично! Теперь отправь мне фото с пивом, чтобы я мог его засчитать. 📸"
        "\nИли отправь /cancel, если передумал."
    )
    
    # Сохраняем ID сообщения и чата для последующего удаления
    context.user_data['prompt_message_id'] = prompt_message.message_id
    context.user_data['prompt_chat_id'] = update.message.chat_id
    
    logger.info(f"Stored prompt message details: message_id={prompt_message.message_id}, chat_id={update.message.chat_id}")
    # Note: We don't return a state here, as the photo handler will trigger the conversation.


async def show_leaderboard_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает таблицу лидеров при нажатии на inline-кнопку."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    chat_id = query.message.chat_id
    user_id = user.id
    
    try:
        # Вызываем логику получения таблицы лидеров напрямую из handlers/leaderboard.py
        from db_utils import get_db, get_leaderboard
        
        with next(get_db()) as db:
            leaderboard_data = get_leaderboard(db, limit=10) # Get top 10

        if not leaderboard_data:
            leaderboard_text = "Таблица лидеров пока пуста. Будь первым! 🍻"
        else:
            leaderboard_text = "🏆 Таблица лидеров Franema Summer Beer Challenge: 🏆\n\n"
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for i, (first_name, username, volume) in enumerate(leaderboard_data, start=1):
                display_name_parts = []
                if first_name:
                    display_name_parts.append(first_name)
                if username:
                    display_name_parts.append(f"(@{username})")
                
                if not display_name_parts:
                    display_name = "Участник"
                else:
                    display_name = " ".join(display_name_parts)

                medal = medals.get(i, f"{i}.") # Get medal or use number
                leaderboard_text += f"{medal} {display_name} - {volume:.2f} л\n"
        
        # Отправляем таблицу как новое сообщение
        await query.message.reply_text(leaderboard_text)
        
    except Exception as e:
        logger.error(f"Error handling leaderboard button click: {e}", exc_info=True)
        await query.message.reply_text("Не удалось загрузить таблицу лидеров. Попробуйте позже.")


async def send_leaderboard_button_to_group(application: Application) -> None:
    """Отправляет сообщение с кнопкой таблицы лидеров в групповой чат."""
    if not GROUP_CHAT_ID:
        logger.warning("GROUP_CHAT_ID not set, cannot send leaderboard button")
        return
    
    # Создаем inline-клавиатуру с кнопкой для таблицы лидеров
    keyboard = [
        [InlineKeyboardButton("🏆 Таблица лидеров 🏆", callback_data="show_leaderboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Отправляем сообщение с кнопкой в групповой чат
        await application.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text="Нажмите на кнопку ниже, чтобы увидеть таблицу лидеров Franema Summer Beer Challenge:",
            reply_markup=reply_markup
        )
        logger.info(f"Leaderboard button message sent to group chat: {GROUP_CHAT_ID}")
    except Exception as e:
        logger.error(f"Failed to send leaderboard button to group chat: {e}", exc_info=True)


async def pin_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение с кнопкой таблицы лидеров в текущий чат и закрепляет его. Только для администраторов."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Проверка на администратора
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user.id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("Эта команда доступна только администраторам чата.")
            return
    except Exception as e:
        logger.error(f"Error checking admin status: {e}", exc_info=True)
        await update.message.reply_text("Не удалось проверить права администратора.")
        return
    
    # Создаем inline-клавиатуру с кнопкой для таблицы лидеров
    keyboard = [
        [InlineKeyboardButton("🏆 Таблица лидеров 🏆", callback_data="show_leaderboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Отправляем сообщение с кнопкой в текущий чат
        message = await context.bot.send_message(
            chat_id=chat_id,
            text="Нажмите на кнопку ниже, чтобы увидеть таблицу лидеров Franema Summer Beer Challenge:",
            reply_markup=reply_markup
        )
        
        # Закрепляем сообщение
        await context.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=message.message_id,
            disable_notification=True
        )
        
        logger.info(f"Leaderboard button message sent and pinned to chat {chat_id}")
        
        # Удаляем оригинальное сообщение с командой
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=update.message.message_id
            )
        except Exception as delete_error:
            logger.error(f"Failed to delete command message: {delete_error}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Failed to send or pin leaderboard button: {e}", exc_info=True)
        await update.message.reply_text("Не удалось отправить или закрепить кнопку таблицы лидеров.")


async def post_init(application: Application) -> None:
    """Устанавливает команды бота после инициализации и планирует завершение конкурса."""
    bot_commands = [
        BotCommand("start", "Начать участие в челлендже"),
        BotCommand("leaderboard", "Показать таблицу лидеров"),
        BotCommand("admin", "Перейти в режим администратора"),
        BotCommand("pin_leaderboard", "Закрепить кнопку таблицы лидеров (только для админов)"),
        BotCommand("announce_winners", "Объявить победителей конкурса (только для админов)")
    ]
    
    # Устанавливаем команды бота для всех чатов
    await application.bot.set_my_commands(bot_commands)
    
    # Больше не отправляем сообщение с кнопкой автоматически при запуске
    # await send_leaderboard_button_to_group(application)
    
    # Планируем задачу объявления победителей конкурса
    # Устанавливаем дату и время окончания конкурса: 31 августа 2025 года в 21:00 по московскому времени
    try:
        from handlers.contest_end import announce_contest_winners
        
        moscow_tz = pytz.timezone('Europe/Moscow')
        end_time = moscow_tz.localize(datetime.datetime(2025, 8, 31, 21, 0, 0))
        
        # Если используем локальное время сервера, конвертируем в UTC
        end_time_utc = end_time.astimezone(pytz.UTC)
        
        # Получаем текущее время для расчета интервала
        now = datetime.datetime.now(pytz.UTC)
        seconds_until_end = (end_time_utc - now).total_seconds()
        
        if seconds_until_end > 0:
            application.job_queue.run_once(
                announce_contest_winners,
                when=seconds_until_end
            )
            logger.info(f"Contest end scheduled for {end_time} (Moscow time)")
        else:
            logger.warning("Contest end date is in the past, not scheduling announcement")
    except Exception as e:
        logger.error(f"Error scheduling contest end: {e}", exc_info=True)
    
    logger.info("Bot commands set successfully")


async def announce_winners_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ручное объявление победителей (только для администраторов)."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Проверка на администратора
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user.id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("Эта команда доступна только администраторам.")
            return
    except Exception as e:
        logger.error(f"Error checking admin status: {e}", exc_info=True)
        await update.message.reply_text("Не удалось проверить права администратора.")
        return
    
    # Подтверждение действия
    await update.message.reply_text(
        "Вы собираетесь объявить победителей конкурса. "
        "Это действие завершит подсчет результатов. Продолжить?"
    )
    
    # Импортируем функцию для объявления победителей
    from handlers.contest_end import announce_contest_winners
    
    # Вызываем функцию объявления победителей
    await announce_contest_winners(context)
    
    # Удаляем исходное сообщение с командой
    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=update.message.message_id
        )
    except Exception as delete_error:
        logger.error(f"Failed to delete command message: {delete_error}", exc_info=True)


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

    # Регистрируем функцию post_init для выполнения после инициализации
    application.post_init = post_init

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    
    # Добавляем команду /leaderboard
    application.add_handler(CommandHandler("leaderboard", show_leaderboard))
    
    # Добавляем команду для закрепления кнопки таблицы лидеров
    application.add_handler(CommandHandler("pin_leaderboard", pin_leaderboard))
    
    # Добавляем команду для ручного объявления победителей
    application.add_handler(CommandHandler("announce_winners", announce_winners_command))

    # Add handlers for the buttons
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^Выпил пиво$'), prompt_for_photo))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^Таблица лидеров$'), show_leaderboard))
    
    # Добавляем обработчик для inline-кнопки таблицы лидеров
    application.add_handler(CallbackQueryHandler(show_leaderboard_button, pattern="^show_leaderboard$"))

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