from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    balance = Column(Float, default=0.0)
    
    # Plans: 'free', 'monthly_25k', 'pack_5_exam'
    # For simplicity, let's track remaining_exams or subscription_end
    subscription_end = Column(DateTime, nullable=True) # For monthly
    exam_credits = Column(Integer, default=0) # For packs
    
    accounts = relationship("GameAccount", back_populates="owner")
    transactions = relationship("Transaction", back_populates="user")
    quiz_sessions = relationship("QuizSession", back_populates="user")

class GameAccount(Base):
    """Represents an Onluyen.vn account managed by the user"""
    __tablename__ = "game_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    name = Column(String) # Display name
    username = Column(String) # Onluyen username
    password = Column(String) # Onluyen password
    
    # Proxy info
    proxy_ip = Column(String, nullable=True)
    proxy_port = Column(String, nullable=True)
    proxy_user = Column(String, nullable=True)
    proxy_pass = Column(String, nullable=True)
    proxy_id = Column(String, nullable=True) # ID from mtdproxy to renew
    
    status = Column(String, default="Offline") # Offline, Ready, Running, Error
    
    owner = relationship("User", back_populates="accounts")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    order_code = Column(String, unique=True)
    status = Column(String, default="PENDING") # PENDING, PAID, CANCELLED
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="transactions")


class QuizSession(Base):
    """Represents a single quiz attempt/session"""
    __tablename__ = "quiz_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    game_account_id = Column(Integer, ForeignKey("game_accounts.id"), nullable=True)
    
    # Quiz metadata
    quiz_name = Column(String)  # e.g., "(KNTT + CD + CTST) Tuần hoàn ở động vật (tổng hợp)"
    quiz_subject = Column(String)  # e.g., "11B5 - SINH HỌC"
    quiz_type = Column(String)  # e.g., "Kiểm tra 45 phút"
    total_questions = Column(Integer, default=0)
    
    # Timing
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)  # When quiz was submitted
    deadline = Column(DateTime, nullable=True)  # Original deadline from assignment
    
    # Results
    total_score = Column(Float, default=0.0)
    max_score = Column(Float, default=0.0)
    percentage = Column(Float, nullable=True)  # Calculated as (total_score / max_score) * 100
    
    # Status: 'in_progress', 'submitted', 'auto_submitted', 'failed'
    status = Column(String, default="in_progress")
    auto_submitted = Column(Boolean, default=False)
    
    # Answers and scores
    answers = relationship("QuizAnswer", back_populates="quiz_session")
    user = relationship("User", back_populates="quiz_sessions")


class QuizAnswer(Base):
    """Represents a single answer within a quiz"""
    __tablename__ = "quiz_answers"
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_session_id = Column(Integer, ForeignKey("quiz_sessions.id"))
    
    # Question info
    question_number = Column(Integer)  # 1, 2, 3, ... or question ID
    question_content = Column(Text, nullable=True)  # Store the question text/image description
    
    # Answer info
    correct_answer = Column(String)  # The correct answer (A/B/C/D)
    student_answer = Column(String, nullable=True)  # What student selected (A/B/C/D)
    is_correct = Column(Boolean, nullable=True)  # True if correct_answer == student_answer
    
    # Scoring
    points_earned = Column(Float, default=0.0)  # e.g., 0.45
    max_points = Column(Float, default=1.0)  # e.g., 1.0
    
    # Metadata
    answer_timestamp = Column(DateTime, default=datetime.utcnow)
    explanation = Column(Text, nullable=True)  # Optional: Gemini explanation for this question
    
    quiz_session = relationship("QuizSession", back_populates="answers")


class AnswerDatabase(Base):
    """Collective answer database for improving accuracy across users"""
    __tablename__ = "answer_database"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Question identification
    question_content_hash = Column(String, unique=True, index=True)  # Hash of question for deduplication
    question_content = Column(Text)  # Full question text/description
    
    # Answer statistics
    answer_a_count = Column(Integer, default=0)
    answer_b_count = Column(Integer, default=0)
    answer_c_count = Column(Integer, default=0)
    answer_d_count = Column(Integer, default=0)
    
    # Most reliable answer (based on stats and correctness)
    most_common_answer = Column(String, nullable=True)  # A/B/C/D
    most_correct_answer = Column(String, nullable=True)  # Based on verified submissions
    confidence = Column(Float, default=0.0)  # 0-1, confidence score
    
    # Metadata
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)
    verified_count = Column(Integer, default=0)  # Number of confirmed correct answers
