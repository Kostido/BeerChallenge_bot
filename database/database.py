import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Путь к директории с базой данных - используем директорию database для совместимости с Render.com
DB_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIRECTORY, "beer_challenge.db")

# Use SQLite database
DATABASE_URL = f"sqlite:///{DB_PATH}"

from models import Base  # Import Base from root models.py

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Function to create database tables
def init_db():
    # Убедимся, что директория существует
    os.makedirs(DB_DIRECTORY, exist_ok=True)
    Base.metadata.create_all(bind=engine)

# Dependency to get DB session in handlers
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()