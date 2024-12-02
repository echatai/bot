from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Teacher(Base):
    __tablename__ = 'teachers'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    telegram_id = Column(String, unique=True, nullable=False)
    active = Column(Boolean, default=True)
    messages = relationship('Message', back_populates='teacher')

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    student_telegram_id = Column(String, nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id'), nullable=False)
    content = Column(String, nullable=False)
    teacher = relationship('Teacher', back_populates='messages')

# اتصال به دیتابیس
import os

engine = create_engine("postgresql://postgres:PqwhhtahibvymXyrmJnsqFyoLUOUhrtc@postgres.railway.internal:5432/railway")
Base.metadata.create_all(engine)
