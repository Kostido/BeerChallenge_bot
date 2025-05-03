#!/usr/bin/env python3
"""
Скрипт для миграции поля photo_file_id в таблице beer_entries,
чтобы оно позволяло хранить значение NULL.
"""

import logging
import os
import sqlite3
from database.database import DB_PATH

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def migrate_photo_field_to_nullable():
    """
    Изменяет таблицу beer_entries, чтобы поле photo_file_id принимало NULL.
    """
    try:
        # Проверяем существование базы данных
        if not os.path.exists(DB_PATH):
            logger.error(f"Database file not found: {DB_PATH}")
            return False
        
        logger.info(f"Starting migration for database: {DB_PATH}")
        
        # Подключаемся к базе данных
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Создаем новую таблицу с нужной схемой
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS beer_entries_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            volume_liters FLOAT NOT NULL,
            photo_file_id VARCHAR,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        
        # Копируем данные из старой таблицы в новую
        cursor.execute("""
        INSERT INTO beer_entries_new (id, user_id, volume_liters, photo_file_id, submitted_at)
        SELECT id, user_id, volume_liters, photo_file_id, submitted_at FROM beer_entries;
        """)
        
        # Удаляем старую таблицу
        cursor.execute("DROP TABLE beer_entries;")
        
        # Переименовываем новую таблицу
        cursor.execute("ALTER TABLE beer_entries_new RENAME TO beer_entries;")
        
        # Создаем индекс для ускорения запросов
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_beer_entries_user_id ON beer_entries (user_id);")
        
        # Сохраняем изменения
        conn.commit()
        logger.info("Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error during migration: {e}", exc_info=True)
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    if migrate_photo_field_to_nullable():
        print("Migration successful: photo_file_id field is now nullable")
    else:
        print("Migration failed. Check logs for details.") 