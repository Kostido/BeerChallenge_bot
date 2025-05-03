#!/usr/bin/env python3
"""Скрипт для отладки функций системы достижений."""

import os
import logging
from handlers.achievements import get_achievement_for_volume, check_new_achievement, format_achievement_message

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

def test_achievements():
    """Тестирует логику проверки достижений."""
    
    # Тестовые объемы пива (старый -> новый)
    test_cases = [
        (0, 0.5),       # Нет достижения
        (0, 1),         # Достижение "Падаван Пивного Ордена"
        (0.9, 1.1),     # Достижение "Падаван Пивного Ордена" 
        (1, 5),         # Достижение "Хоббит из Шира"
        (4, 5.5),       # Достижение "Хоббит из Шира"
        (5, 9),         # Нет нового достижения
        (9, 11),        # Достижение "Страж Пенного Стана"
        (11, 20),       # Достижение "Пивной Фалкон"
        (30, 40),       # Достижение "Хмельной Джек Воробей"
        (49, 51),       # Достижение "Пивной Гэндальф"
        (50, 75),       # Достижение "Хмелевой Джокер"
        (70, 101),      # Достижение "Пенный Доктор Стрэндж"
    ]
    
    logger.info("Начинаю тестирование системы достижений...")
    
    for i, (old_volume, new_volume) in enumerate(test_cases):
        logger.info(f"Тест #{i+1}: старый объем = {old_volume}, новый объем = {new_volume}")
        
        # Получаем достижения для обоих объемов
        old_achievement = get_achievement_for_volume(old_volume)
        new_achievement = get_achievement_for_volume(new_volume)
        
        if old_achievement:
            logger.info(f"  Старое достижение: {old_achievement['title']} ({old_achievement['volume']} л)")
        else:
            logger.info("  Нет старого достижения")
            
        if new_achievement:
            logger.info(f"  Новое достижение: {new_achievement['title']} ({new_achievement['volume']} л)")
        else:
            logger.info("  Нет нового достижения")
        
        # Проверяем, есть ли новое достижение
        achievement = check_new_achievement(old_volume, new_volume)
        if achievement:
            message = format_achievement_message(achievement, "@test_user")
            logger.info(f"  ✅ ПОЛУЧЕНО НОВОЕ ДОСТИЖЕНИЕ: {achievement['title']}")
            logger.info(f"  Сообщение: {message}")
            
            # Проверяем существование файла изображения
            if os.path.exists(achievement['image']):
                logger.info(f"  Файл изображения найден: {achievement['image']}")
            else:
                logger.error(f"  ❌ Файл изображения НЕ найден: {achievement['image']}")
        else:
            logger.info("  ❌ Нет нового достижения")
        
        logger.info("-" * 60)

if __name__ == "__main__":
    test_achievements() 