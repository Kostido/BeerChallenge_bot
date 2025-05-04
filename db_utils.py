# db_utils.py
import logging
import os
import sys
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

# Добавляем обработку различных путей импорта для повышения надежности
try:
    from database.database import SessionLocal
except ImportError:
    # Пробуем другой вариант импорта, если находимся в корне проекта
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from database.database import SessionLocal
    except ImportError:
        # Последняя попытка с относительным импортом
        from .database.database import SessionLocal

from models import User, BeerEntry

logger = logging.getLogger(__name__)

def get_db():
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def add_or_update_user(db: Session, user_id: int, first_name: Optional[str], username: Optional[str]) -> User:
    """Adds a new user or updates existing user's info."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user:
        # Update info if changed
        if db_user.first_name != first_name or db_user.username != username:
            db_user.first_name = first_name
            db_user.username = username
            logger.info(f"Updated user info for {user_id}")
    else:
        db_user = User(id=user_id, first_name=first_name, username=username)
        db.add(db_user)
        logger.info(f"Added new user: {user_id} ({username or first_name}) ")
    db.commit()
    db.refresh(db_user)
    return db_user

def add_beer_entry(db: Session, user_id: int, volume: float, photo_id: str = None) -> BeerEntry:
    """
    Adds a new beer entry for a user.
    
    Args:
        db (Session): Database session
        user_id (int): User ID
        volume (float): Volume of beer in liters
        photo_id (str, optional): Telegram photo file ID or special value for initial entry
        
    Returns:
        BeerEntry: Created database entry
    """
    # Ensure user exists (optional, depends on workflow)
    # user = db.query(User).filter(User.id == user_id).first()
    # if not user:
    #     logger.error(f"Attempted to add beer entry for non-existent user {user_id}")
    #     # Handle this case appropriately, maybe raise an error or return None
    #     return None

    db_entry = BeerEntry(user_id=user_id, volume_liters=volume, photo_file_id=photo_id)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    logger.info(f"Added beer entry for user {user_id}: {volume}L, photo: {photo_id}")
    return db_entry

def get_leaderboard(db: Session, limit: int = 10) -> List[Tuple[Optional[str], Optional[str], float]]:
    """Gets the leaderboard data (top users by total volume), returning first_name, username, and volume."""
    results = (
        db.query(
            User.first_name,
            User.username, # Add username
            func.sum(BeerEntry.volume_liters).label('total_volume')
        )
        .join(BeerEntry, User.id == BeerEntry.user_id)
        .group_by(User.id, User.first_name, User.username) # Group by username as well
        .order_by(desc('total_volume'))
        .limit(limit)
        .all()
    )
    # Return first_name, username, and volume
    leaderboard = [(first_name, username, volume) for first_name, username, volume in results]
    return leaderboard

def get_user_total_volume(db: Session, user_id: int) -> float:
    """
    Получает общий объем выпитого пива пользователем.
    
    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        
    Returns:
        float: Общий объем выпитого пива в литрах
    """
    result = (
        db.query(func.sum(BeerEntry.volume_liters).label('total_volume'))
        .filter(BeerEntry.user_id == user_id)
        .scalar()
    )
    return result or 0.0  # Возвращаем 0, если у пользователя еще нет записей