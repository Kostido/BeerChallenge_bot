#!/usr/bin/env python3
"""
Скрипт для автоматического резервного копирования базы данных SQLite.
Копирует файл базы данных и сохраняет его с меткой времени.
Также позволяет восстановить базу данных из бэкапа.
"""
import os
import sys
import shutil
import sqlite3
import argparse
import datetime
import glob
import logging

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Пути к файлам и директориям
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, 'beer_challenge.db')
BACKUP_DIR = os.path.join(SCRIPT_DIR, 'backups')

def setup_backup_dir():
    """Создаёт директорию для резервных копий, если она не существует."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        logger.info(f"Создана директория для резервных копий: {BACKUP_DIR}")

def create_backup():
    """Создаёт резервную копию базы данных с текущей датой и временем."""
    setup_backup_dir()
    
    # Проверяем, существует ли файл базы данных
    if not os.path.exists(DB_FILE):
        logger.error(f"Файл базы данных не найден: {DB_FILE}")
        return False
    
    # Создаём имя файла резервной копии с текущей датой и временем
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"beer_challenge_{timestamp}.db")
    
    try:
        # Перед копированием проверяем целостность базы данных
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]
        conn.close()
        
        if integrity_result != "ok":
            logger.error(f"База данных повреждена: {integrity_result}")
            return False
        
        # Копируем файл базы данных
        shutil.copy2(DB_FILE, backup_file)
        logger.info(f"Создана резервная копия: {backup_file}")
        
        # Удаляем старые резервные копии (оставляем только 10 последних)
        cleanup_old_backups()
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании резервной копии: {e}")
        return False

def list_backups():
    """Выводит список доступных резервных копий."""
    setup_backup_dir()
    
    backup_files = sorted(glob.glob(os.path.join(BACKUP_DIR, "beer_challenge_*.db")))
    
    if not backup_files:
        logger.info("Резервные копии не найдены.")
        return []
    
    logger.info("Доступные резервные копии:")
    for i, file in enumerate(backup_files, 1):
        filename = os.path.basename(file)
        size = os.path.getsize(file) / 1024  # размер в КБ
        logger.info(f"{i}. {filename} ({size:.2f} КБ)")
    
    return backup_files

def restore_backup(backup_file):
    """Восстанавливает базу данных из указанной резервной копии."""
    if not os.path.exists(backup_file):
        logger.error(f"Файл резервной копии не найден: {backup_file}")
        return False
    
    try:
        # Проверяем целостность резервной копии
        conn = sqlite3.connect(backup_file)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]
        conn.close()
        
        if integrity_result != "ok":
            logger.error(f"Резервная копия повреждена: {integrity_result}")
            return False
        
        # Создаем резервную копию текущей БД перед восстановлением
        current_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        current_backup = os.path.join(BACKUP_DIR, f"pre_restore_{current_timestamp}.db")
        
        if os.path.exists(DB_FILE):
            shutil.copy2(DB_FILE, current_backup)
            logger.info(f"Создана резервная копия текущей БД: {current_backup}")
        
        # Восстанавливаем из резервной копии
        shutil.copy2(backup_file, DB_FILE)
        logger.info(f"База данных восстановлена из: {backup_file}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при восстановлении базы данных: {e}")
        return False

def cleanup_old_backups(keep=10):
    """Удаляет старые резервные копии, оставляя только указанное количество последних."""
    backup_files = sorted(glob.glob(os.path.join(BACKUP_DIR, "beer_challenge_*.db")))
    
    if len(backup_files) <= keep:
        return
    
    for old_file in backup_files[:-keep]:
        try:
            os.remove(old_file)
            logger.info(f"Удалена старая резервная копия: {old_file}")
        except Exception as e:
            logger.error(f"Ошибка при удалении старой резервной копии: {e}")

def main():
    parser = argparse.ArgumentParser(description="Утилита для резервного копирования и восстановления базы данных.")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--backup', action='store_true', help='Создать резервную копию базы данных')
    group.add_argument('--list', action='store_true', help='Показать список доступных резервных копий')
    group.add_argument('--restore', metavar='BACKUP_FILE', help='Восстановить базу данных из указанной резервной копии')
    group.add_argument('--restore-latest', action='store_true', help='Восстановить из последней резервной копии')
    
    args = parser.parse_args()
    
    if args.backup:
        if create_backup():
            print("Резервная копия успешно создана.")
        else:
            print("Не удалось создать резервную копию.")
            sys.exit(1)
    
    elif args.list:
        backup_files = list_backups()
        if not backup_files:
            print("Резервные копии не найдены.")
    
    elif args.restore:
        if restore_backup(args.restore):
            print(f"База данных успешно восстановлена из {args.restore}.")
        else:
            print(f"Не удалось восстановить базу данных из {args.restore}.")
            sys.exit(1)
    
    elif args.restore_latest:
        backup_files = sorted(glob.glob(os.path.join(BACKUP_DIR, "beer_challenge_*.db")))
        
        if not backup_files:
            print("Резервные копии не найдены.")
            sys.exit(1)
        
        latest_backup = backup_files[-1]
        if restore_backup(latest_backup):
            print(f"База данных успешно восстановлена из последней копии: {latest_backup}.")
        else:
            print(f"Не удалось восстановить базу данных из {latest_backup}.")
            sys.exit(1)

if __name__ == "__main__":
    main() 