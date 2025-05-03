# handlers/achievements.py
"""Модуль для работы с достижениями пивного челленджа."""
import os

# Путь к папке с изображениями достижений
ASSETS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')

# Список достижений по объему выпитого пива (в литрах)
ACHIEVEMENTS = [
    {
        "volume": 1,
        "title": "Падаван Пивного Ордена",
        "message": "Сила пива с тобой, но ты еще не джедай кружки! 🚀",
        "icon": "🚀",
        "image": os.path.join(ASSETS_PATH, "Падаван Пивного Ордена.jpg")
    },
    {
        "volume": 5,
        "title": "Хоббит из Шира",
        "message": "Ты только начал попивать эль в таверне Зеленого Дракона! 🧙‍♂️",
        "icon": "🧙‍♂️",
        "image": os.path.join(ASSETS_PATH, "Хоббит из Шира.png")
    },
    {
        "volume": 10,
        "title": "Страж Пенного Стана",
        "message": "Ты защищаешь бар от трезвенников, но зима близко! 🐺",
        "icon": "🐺",
        "image": os.path.join(ASSETS_PATH, "Страж Пенного Стана.jpg")
    },
    {
        "volume": 20,
        "title": "Пивной Фалкон",
        "message": "Твоя кружка пролетает пивной гиперпространственный маршрут за 12 парсеков! 🛸",
        "icon": "🛸",
        "image": os.path.join(ASSETS_PATH, "Пивной Фалкон.jpg")
    },
    {
        "volume": 30,
        "title": "Герой Пивного Шилдена",
        "message": "Ты поднял молот пены и достоин тоста с Тором! ⚡",
        "icon": "⚡",
        "image": os.path.join(ASSETS_PATH, "Герой Пивного Шилдена.jpg")
    },
    {
        "volume": 40,
        "title": "Хмельной Джек Воробей",
        "message": "Где твое пиво? Почему его нет? А, вот оно, в твоем желудке! 🏴‍☠️",
        "icon": "🏴‍☠️",
        "image": os.path.join(ASSETS_PATH, "Хмельной Джек Воробей.jpg")
    },
    {
        "volume": 50,
        "title": "Пивной Гэндальф",
        "message": "Ты прошел через пабы и пены, и вышел с полным бокалом! 🧙‍♂️",
        "icon": "🧙‍♂️",
        "image": os.path.join(ASSETS_PATH, "Пивной Гэндальф 2.png")
    },
    {
        "volume": 75,
        "title": "Хмелевой Джокер",
        "message": "Почему так серьезно? Давай нальем еще пива и устроим хаос! 🃏",
        "icon": "🃏",
        "image": os.path.join(ASSETS_PATH, "Хмелевой Джокер.png")
    },
    {
        "volume": 100,
        "title": "Пенный Доктор Стрэндж",
        "message": "Ты освоил мультивселенную пива и открыл портал в хмельной рай! 🌀",
        "icon": "🌀",
        "image": os.path.join(ASSETS_PATH, "Пенный Доктор Стрэндж.png")
    }
]

def get_achievement_for_volume(total_volume):
    """
    Возвращает достижение для указанного объема пива.
    
    Args:
        total_volume (float): Общий объем выпитого пива
        
    Returns:
        dict or None: Словарь с информацией о достижении или None, если достижение не найдено
    """
    current_achievement = None
    
    # Находим самое высокое достижение, которое соответствует объему
    for achievement in ACHIEVEMENTS:
        if total_volume >= achievement["volume"]:
            current_achievement = achievement
        else:
            # Список отсортирован по возрастанию объема, 
            # так что можно прервать цикл, когда находим объем больше текущего
            break
    
    return current_achievement

def check_new_achievement(old_volume, new_volume):
    """
    Проверяет, достиг ли пользователь нового достижения.
    
    Args:
        old_volume (float): Старый общий объем выпитого пива
        new_volume (float): Новый общий объем выпитого пива
        
    Returns:
        dict or None: Словарь с информацией о новом достижении или None, если нет нового достижения
    """
    old_achievement = get_achievement_for_volume(old_volume)
    new_achievement = get_achievement_for_volume(new_volume)
    
    # Если достижение изменилось, значит получено новое
    if new_achievement and (not old_achievement or old_achievement["volume"] < new_achievement["volume"]):
        return new_achievement
    
    return None

def format_achievement_message(achievement, username):
    """
    Форматирует сообщение о достижении.
    
    Args:
        achievement (dict): Словарь с информацией о достижении
        username (str): Имя пользователя
        
    Returns:
        str: Отформатированное сообщение о достижении
    """
    return (f"🏆 НОВОЕ ДОСТИЖЕНИЕ! 🏆\n\n"
            f"{username} достиг(ла) звания «{achievement['title']}»!\n"
            f"{achievement['message']}\n\n"
            f"Объем выпитого пива: {achievement['volume']}+ литров") 