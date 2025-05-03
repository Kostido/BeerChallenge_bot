#!/usr/bin/env python3
"""
Скрипт для резервного копирования и восстановления базы данных.
Позволяет сохранить базу данных перед редеплоем и восстановить её после.
"""

import os
import sys
import json
import logging
import argparse
import sqlite3
import datetime
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем путь к директории базы данных
if os.environ.get('RENDER'):
    DB_DIRECTORY = '/app/database'
else:
    DB_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database')

DB_PATH = os.path.join(DB_DIRECTORY, "beer_challenge.db")
BACKUP_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')

def ensure_backup_dir():
    """Создает директорию для резервных копий, если она не существует."""
    os.makedirs(BACKUP_DIRECTORY, exist_ok=True)
    logger.info(f"Backup directory ensured: {BACKUP_DIRECTORY}")

def backup_database():
    """Создает резервную копию базы данных в JSON формате."""
    ensure_backup_dir()
    
    # Проверяем существование базы данных
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file not found: {DB_PATH}")
        return False
    
    # Создаем имя файла резервной копии с датой и временем
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIRECTORY, f"beer_challenge_backup_{timestamp}.json")
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row['name'] for row in cursor.fetchall()]
        
        # Создаем структуру данных для резервной копии
        backup_data = {}
        
        # Для каждой таблицы получаем данные
        for table in tables:
            if table == 'sqlite_sequence':
                continue  # Пропускаем служебную таблицу SQLite
                
            cursor.execute(f"SELECT * FROM {table};")
            columns = [desc[0] for desc in cursor.description]
            rows = []
            
            for row in cursor.fetchall():
                rows.append(dict(zip(columns, row)))
            
            backup_data[table] = rows
        
        # Записываем данные в JSON файл
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Database backup created: {backup_file}")
        return backup_file
        
    except Exception as e:
        logger.error(f"Error creating database backup: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def restore_database(backup_file=None):
    """Восстанавливает базу данных из резервной копии."""
    # Если файл не указан, используем последний созданный
    if not backup_file:
        backup_files = sorted(
            [f for f in os.listdir(BACKUP_DIRECTORY) if f.startswith('beer_challenge_backup_')],
            reverse=True
        )
        if not backup_files:
            logger.error("No backup files found")
            return False
        
        backup_file = os.path.join(BACKUP_DIRECTORY, backup_files[0])
    
    # Проверяем существование файла резервной копии
    if not os.path.exists(backup_file):
        logger.error(f"Backup file not found: {backup_file}")
        return False
    
    try:
        # Загружаем данные из JSON файла
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        # Убеждаемся, что директория для базы данных существует
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # Подключаемся к базе данных (создаем новую, если не существует)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Для каждой таблицы в резервной копии
        for table, rows in backup_data.items():
            if not rows:
                logger.info(f"No data for table {table}, skipping...")
                continue
            
            # Получаем схему таблицы из первой строки
            columns = list(rows[0].keys())
            
            # Создаем таблицу, если она не существует
            create_query = f"CREATE TABLE IF NOT EXISTS {table} ("
            create_query += ", ".join([f"{col} TEXT" for col in columns])
            create_query += ");"
            cursor.execute(create_query)
            
            # Вставляем данные построчно
            for row in rows:
                placeholders = ", ".join(["?" for _ in columns])
                insert_query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders});"
                values = [row.get(col) for col in columns]
                cursor.execute(insert_query, values)
        
        # Сохраняем изменения
        conn.commit()
        logger.info(f"Database restored from: {backup_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error restoring database: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """Основная функция скрипта."""
    parser = argparse.ArgumentParser(description="Database backup and restore tool")
    parser.add_argument('action', choices=['backup', 'restore'], help="Action to perform")
    parser.add_argument('--file', help="Backup file to restore from (for restore action)")
    
    args = parser.parse_args()
    
    if args.action == 'backup':
        backup_file = backup_database()
        if backup_file:
            print(f"Backup created: {backup_file}")
        else:
            print("Backup failed")
    elif args.action == 'restore':
        success = restore_database(args.file)
        if success:
            print("Database restored successfully")
        else:
            print("Restore failed")

if __name__ == "__main__":
    main() 