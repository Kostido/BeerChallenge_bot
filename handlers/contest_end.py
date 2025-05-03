"""
Модуль для функций, связанных с окончанием конкурса и объявлением победителей.
"""
import logging
from telegram.ext import ContextTypes
from config import GROUP_CHAT_ID

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def announce_contest_winners(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Объявляет победителей конкурса в групповой чат после окончания челленджа."""
    if not GROUP_CHAT_ID:
        logger.error("GROUP_CHAT_ID not set, cannot announce winners")
        return
    
    try:
        # Получаем таблицу лидеров с тремя лучшими участниками
        from db_utils import get_db, get_leaderboard
        
        with next(get_db()) as db:
            top_winners = get_leaderboard(db, limit=3)
        
        if not top_winners:
            await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text="🏆 Franema Summer Beer Challenge завершен! 🏆\n\nК сожалению, никто не принял участие в челлендже. Будем ждать следующего лета!"
            )
            return
        
        # Формируем сообщение с победителями
        winners_text = "🎉 Franema Summer Beer Challenge завершен! 🎉\n\n"
        winners_text += "🏆 Наши победители: 🏆\n\n"
        
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        
        for i, (first_name, username, volume) in enumerate(top_winners, start=1):
            display_name_parts = []
            if first_name:
                display_name_parts.append(first_name)
            if username:
                display_name_parts.append(f"(@{username})")
            
            if not display_name_parts:
                display_name = "Участник"
            else:
                display_name = " ".join(display_name_parts)
            
            medal = medals.get(i, f"{i}.")
            winners_text += f"{medal} {display_name} - {volume:.2f} л\n"
        
        total_participants = 0
        total_volume = 0.0
        
        with next(get_db()) as db:
            # Получаем статистику конкурса
            try:
                from sqlalchemy import func, distinct
                from models import User, BeerEntry
                
                total_participants = db.query(func.count(distinct(User.id))).scalar() or 0
                total_volume = db.query(func.sum(BeerEntry.volume)).scalar() or 0.0
            except Exception as stats_error:
                logger.error(f"Error getting contest stats: {stats_error}", exc_info=True)
                total_participants = len(top_winners)
                total_volume = sum(winner[2] for winner in top_winners)
        
        winners_text += f"\n🍻 Всего участников: {total_participants}"
        winners_text += f"\n🍺 Общий объем выпитого пива: {total_volume:.2f} л"
        winners_text += "\n\nСпасибо всем за участие! До следующего лета! 🌞"
        
        # Отправляем сообщение с результатами
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=winners_text
        )
        logger.info("Contest winners announced successfully")
        
    except Exception as e:
        logger.error(f"Error announcing contest winners: {e}", exc_info=True)
        # Попытка отправить сообщение об ошибке
        try:
            await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text="Произошла ошибка при подведении итогов конкурса. Пожалуйста, свяжитесь с администратором."
            )
        except Exception as notify_error:
            logger.error(f"Error sending error notification: {notify_error}", exc_info=True) 