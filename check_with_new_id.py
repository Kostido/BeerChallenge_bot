#!/usr/bin/env python3
"""Скрипт для проверки нового ID группового чата."""

import os

# Жестко кодируем новый ID для тестирования
os.environ["GROUP_CHAT_ID"] = "-1002506753369"

# Получаем значения переменных
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID")

print("====== Проверка нового ID группового чата ======")
print(f"GROUP_CHAT_ID: {GROUP_CHAT_ID}")

# Проверяем формат GROUP_CHAT_ID
if GROUP_CHAT_ID:
    # GROUP_CHAT_ID должен быть числом, возможно с минусом спереди
    try:
        chat_id = int(GROUP_CHAT_ID)
        print(f"GROUP_CHAT_ID валидный: {chat_id} (тип: {type(chat_id)})")
        print("✅ Этот ID имеет правильный формат и может быть использован в .env файле.")
    except ValueError:
        print(f"ОШИБКА: GROUP_CHAT_ID имеет неверный формат: {GROUP_CHAT_ID}")
else:
    print("ВНИМАНИЕ: GROUP_CHAT_ID не установлен.")
    
print("=================================================") 