# models.py
from sqlalchemy import create_engine, Column, Integer, String, Float, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True, index=True) # Telegram User ID
    first_name = Column(String, nullable=True)
    username = Column(String, nullable=True, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    beer_entries = relationship("BeerEntry", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"

class BeerEntry(Base):
    __tablename__ = 'beer_entries'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    volume_liters = Column(Float, nullable=False)
    photo_file_id = Column(String, nullable=True)  # Разрешаем NULL для начальных записей
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="beer_entries")

    def __repr__(self):
        return f"<BeerEntry(id={self.id}, user_id={self.user_id}, volume={self.volume_liters})>"