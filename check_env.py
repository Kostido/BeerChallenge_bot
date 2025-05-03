#!/usr/bin/env python3
"""Скрипт для проверки переменных окружения."""

import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Получаем значения переменных
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

print("====== Проверка переменных окружения ======")
print(f"BOT_TOKEN: {'УСТАНОВЛЕН' if BOT_TOKEN else 'НЕ УСТАНОВЛЕН'}")
print(f"GROUP_CHAT_ID: {GROUP_CHAT_ID or 'НЕ УСТАНОВЛЕН'}")

# Проверяем формат GROUP_CHAT_ID
if GROUP_CHAT_ID:
    # GROUP_CHAT_ID должен быть числом, возможно с минусом спереди
    try:
        chat_id = int(GROUP_CHAT_ID)
        print(f"GROUP_CHAT_ID валидный: {chat_id} (тип: {type(chat_id)})")
    except ValueError:
        print(f"ОШИБКА: GROUP_CHAT_ID имеет неверный формат: {GROUP_CHAT_ID}")
else:
    print("ВНИМАНИЕ: GROUP_CHAT_ID не установлен. Уведомления в групповой чат отправляться не будут!")
    
print("===========================================") 