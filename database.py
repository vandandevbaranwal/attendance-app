import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")

# Automatically fix postgresql protocol name if using a cloud DB like Neon or Render
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite requires check_same_thread=False, PostgreSQL does not support it
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    roll_number = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)

    attendances = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")

class ClassroomSession(Base):
    __tablename__ = "classroom_sessions"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    session_date = Column(String, nullable=False)  # format YYYY-MM-DD
    is_active = Column(Integer, default=1, nullable=False)  # 1 for active, 0 for inactive
    started_at = Column(DateTime, nullable=False)
    current_token = Column(String, nullable=False)
    previous_tokens = Column(String, nullable=True)  # Comma-separated list of older valid tokens
    token_expiry = Column(DateTime, nullable=False)

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    subject = Column(String, nullable=False)

    student = relationship("Student", back_populates="attendances")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
