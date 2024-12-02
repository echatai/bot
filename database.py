from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# اتصال به پایگاه داده PostgreSQL
import os
engine = create_engine("postgresql://postgres:FcFpDSqKJHgzyORXZsGobHJPhVNAwXxW@postgres.railway.internal:5432/railway", echo=True)

Base = declarative_base()

# مدل جدول Teacher
class Teacher(Base):
    __tablename__ = 'teachers'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    active = Column(Boolean, default=True)

    # رابطه یک معلم با پیام‌ها
    messages = relationship("Message", back_populates="teacher", cascade="all, delete-orphan")

# مدل جدول Message
class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    student_telegram_id = Column(String, nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id'), nullable=False)
    content = Column(String, nullable=False)

    # رابطه پیام‌ها با معلم
    teacher = relationship("Teacher", back_populates="messages")

# ایجاد جداول در پایگاه داده
Base.metadata.create_all(engine)

# تنظیمات Session برای ارتباط با پایگاه داده
Session = sessionmaker(bind=engine)
session = Session()
