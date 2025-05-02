from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Use SQLite database
DATABASE_URL = "sqlite:///beer_challenge.db"

from models import Base  # Import Base from root models.py

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Function to create database tables
def init_db():
    Base.metadata.create_all(bind=engine)

# Dependency to get DB session in handlers
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()