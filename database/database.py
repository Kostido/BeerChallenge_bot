import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определяем путь к директории с базой данных
# В Render.com постоянный диск монтируется по пути /app/database
# Проверяем, запущены ли мы в Render.com (проверка переменной окружения RENDER)
if os.environ.get('RENDER'):
    # Путь для Render.com с постоянным диском
    DB_DIRECTORY = '/app/database'
    logger.info("Running on Render.com, using persistent disk at: %s", DB_DIRECTORY)
else:
    # Локальный путь для разработки
    DB_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    logger.info("Running locally, using database directory: %s", DB_DIRECTORY)

DB_PATH = os.path.join(DB_DIRECTORY, "beer_challenge.db")
logger.info("Database path: %s", DB_PATH)

# Use SQLite database
DATABASE_URL = f"sqlite:///{DB_PATH}"

from models import Base  # Import Base from root models.py

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Function to create database tables
def init_db():
    # Убедимся, что директория существует
    os.makedirs(DB_DIRECTORY, exist_ok=True)
    logger.info("Ensuring database directory exists: %s", DB_DIRECTORY)
    
    # Создаем таблицы, если они не существуют
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/checked at: %s", DB_PATH)

# Dependency to get DB session in handlers
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()