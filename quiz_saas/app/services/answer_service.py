"""
Answer Service - Handles saving and managing quiz answers
Provides functionality for:
1. Saving quiz answers with per-question scores
2. Auto-detecting incomplete assignments
3. Retrieving answer database for solving
4. Auto-submitting quizzes when time expires
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import hashlib
import json
from ..models import (
    QuizSession, QuizAnswer, AnswerDatabase, User, GameAccount
)


class AnswerService:
    """Service for managing quiz answers and sessions"""
    
    @staticmethod
    def create_quiz_session(
        db: Session,
        user_id: int,
        quiz_name: str,
        quiz_subject: str,
        quiz_type: str,
        total_questions: int,
        max_score: float = None,
        deadline: datetime = None,
        game_account_id: int = None
    ) -> QuizSession:
        """
        Create a new quiz session when starting a quiz
        
        Args:
            db: Database session
            user_id: ID of user taking the quiz
            quiz_name: Name of the quiz (e.g., "Tuần hoàn ở động vật")
            quiz_subject: Subject code (e.g., "11B5 - SINH HỌC")
            quiz_type: Type of quiz (e.g., "Kiểm tra 45 phút")
            total_questions: Total number of questions
            max_score: Maximum possible score (optional)
            deadline: Deadline for the quiz (optional)
            game_account_id: Associated game account (optional)
            
        Returns:
            QuizSession object
        """
        session = QuizSession(
            user_id=user_id,
            game_account_id=game_account_id,
            quiz_name=quiz_name,
            quiz_subject=quiz_subject,
            quiz_type=quiz_type,
            total_questions=total_questions,
            max_score=max_score or total_questions,  # Default: 1 point per question
            deadline=deadline,
            start_time=datetime.utcnow(),
            status="in_progress"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    
    @staticmethod
    def save_answer(
        db: Session,
        quiz_session_id: int,
        question_number: int,
        correct_answer: str,
        student_answer: str = None,
        points_earned: float = 0.0,
        max_points: float = 1.0,
        question_content: str = None,
        explanation: str = None
    ) -> QuizAnswer:
        """
        Save a single answer to the database
        
        Args:
            db: Database session
            quiz_session_id: ID of the quiz session
            question_number: Question number (1, 2, 3, ...)
            correct_answer: The correct answer (A/B/C/D)
            student_answer: Student's selected answer (A/B/C/D)
            points_earned: Points earned for this question (e.g., 0.45)
            max_points: Maximum points for this question (default 1.0)
            question_content: Store question text/description
            explanation: Optional explanation from Gemini
            
        Returns:
            QuizAnswer object
        """
        is_correct = None
        if student_answer:
            is_correct = (student_answer.upper() == correct_answer.upper())
        
        answer = QuizAnswer(
            quiz_session_id=quiz_session_id,
            question_number=question_number,
            question_content=question_content,
            correct_answer=correct_answer.upper(),
            student_answer=student_answer.upper() if student_answer else None,
            is_correct=is_correct,
            points_earned=points_earned,
            max_points=max_points,
            answer_timestamp=datetime.utcnow(),
            explanation=explanation
        )
        db.add(answer)
        db.commit()
        db.refresh(answer)
        
        # Update answer database with this answer
        AnswerService.update_answer_database(
            db, question_content, correct_answer, is_correct
        )
        
        return answer
    
    @staticmethod
    def finalize_quiz_session(
        db: Session,
        quiz_session_id: int,
        auto_submitted: bool = False
    ) -> QuizSession:
        """
        Finalize a quiz session after completion
        Calculates final score and updates session status
        
        Args:
            db: Database session
            quiz_session_id: ID of the quiz session
            auto_submitted: Whether this was auto-submitted
            
        Returns:
            Updated QuizSession object
        """
        session = db.query(QuizSession).filter(
            QuizSession.id == quiz_session_id
        ).first()
        
        if not session:
            raise ValueError(f"Quiz session {quiz_session_id} not found")
        
        # Calculate total score from all answers
        answers = db.query(QuizAnswer).filter(
            QuizAnswer.quiz_session_id == quiz_session_id
        ).all()
        
        total_score = sum(a.points_earned for a in answers)
        percentage = (total_score / session.max_score * 100) if session.max_score > 0 else 0
        
        session.end_time = datetime.utcnow()
        session.total_score = total_score
        session.percentage = percentage
        session.auto_submitted = auto_submitted
        session.status = "auto_submitted" if auto_submitted else "submitted"
        
        db.commit()
        db.refresh(session)
        return session
    
    @staticmethod
    def update_answer_database(
        db: Session,
        question_content: str,
        correct_answer: str,
        is_correct: bool = None
    ) -> AnswerDatabase:
        """
        Update the collective answer database with this answer
        Used for building answer statistics across all users
        
        Args:
            db: Database session
            question_content: The question text/description
            correct_answer: The correct answer (A/B/C/D)
            is_correct: Whether this answer was marked correct
            
        Returns:
            AnswerDatabase object (created or updated)
        """
        if not question_content:
            return None
        
        # Create hash of question for deduplication
        question_hash = hashlib.md5(
            question_content.encode('utf-8')
        ).hexdigest()
        
        answer_db = db.query(AnswerDatabase).filter(
            AnswerDatabase.question_content_hash == question_hash
        ).first()
        
        if not answer_db:
            answer_db = AnswerDatabase(
                question_content_hash=question_hash,
                question_content=question_content
            )
            db.add(answer_db)
        
        # Update answer counts
        letter = correct_answer.upper()
        if letter == 'A':
            answer_db.answer_a_count += 1
        elif letter == 'B':
            answer_db.answer_b_count += 1
        elif letter == 'C':
            answer_db.answer_c_count += 1
        elif letter == 'D':
            answer_db.answer_d_count += 1
        
        # Update verified count if marked correct
        if is_correct:
            answer_db.verified_count += 1
            answer_db.most_correct_answer = letter
        
        # Calculate most common answer
        counts = {
            'A': answer_db.answer_a_count,
            'B': answer_db.answer_b_count,
            'C': answer_db.answer_c_count,
            'D': answer_db.answer_d_count
        }
        answer_db.most_common_answer = max(counts, key=counts.get)
        
        # Calculate confidence (ratio of verified correct to total)
        total_answers = sum(counts.values())
        if total_answers > 0:
            answer_db.confidence = answer_db.verified_count / total_answers
        
        answer_db.last_updated = datetime.utcnow()
        db.commit()
        db.refresh(answer_db)
        return answer_db
    
    @staticmethod
    def get_quiz_history(
        db: Session,
        user_id: int,
        limit: int = 20
    ) -> list:
        """
        Get quiz history for a user
        
        Args:
            db: Database session
            user_id: ID of user
            limit: Maximum number of records to return
            
        Returns:
            List of QuizSession objects, newest first
        """
        return db.query(QuizSession).filter(
            QuizSession.user_id == user_id
        ).order_by(
            QuizSession.start_time.desc()
        ).limit(limit).all()
    
    @staticmethod
    def get_quiz_details(
        db: Session,
        quiz_session_id: int
    ) -> dict:
        """
        Get detailed info about a quiz session including all answers
        
        Args:
            db: Database session
            quiz_session_id: ID of the quiz session
            
        Returns:
            Dictionary with session details and answers
        """
        session = db.query(QuizSession).filter(
            QuizSession.id == quiz_session_id
        ).first()
        
        if not session:
            return None
        
        answers = db.query(QuizAnswer).filter(
            QuizAnswer.quiz_session_id == quiz_session_id
        ).order_by(QuizAnswer.question_number).all()
        
        return {
            "session": session,
            "answers": answers,
            "total_questions": session.total_questions,
            "total_score": session.total_score,
            "max_score": session.max_score,
            "percentage": session.percentage,
            "correct_count": sum(1 for a in answers if a.is_correct),
            "duration_seconds": (
                (session.end_time - session.start_time).total_seconds()
                if session.end_time else None
            )
        }
    
    @staticmethod
    def get_answer_database(
        db: Session,
        question_content: str = None,
        min_confidence: float = 0.5
    ) -> list:
        """
        Get answer suggestions from the collective database
        
        Args:
            db: Database session
            question_content: Optional filter by question content
            min_confidence: Minimum confidence threshold (0-1)
            
        Returns:
            List of AnswerDatabase records matching criteria
        """
        query = db.query(AnswerDatabase).filter(
            AnswerDatabase.confidence >= min_confidence
        )
        
        if question_content:
            question_hash = hashlib.md5(
                question_content.encode('utf-8')
            ).hexdigest()
            query = query.filter(
                AnswerDatabase.question_content_hash == question_hash
            )
        
        return query.all()
    
    @staticmethod
    def check_time_expiry(deadline: datetime) -> bool:
        """
        Check if quiz deadline has passed
        
        Args:
            deadline: Deadline datetime
            
        Returns:
            True if time has expired, False otherwise
        """
        if not deadline:
            return False
        return datetime.utcnow() >= deadline
    
    @staticmethod
    def get_time_remaining(deadline: datetime) -> dict:
        """
        Get time remaining until deadline
        
        Args:
            deadline: Deadline datetime
            
        Returns:
            Dictionary with time info (total_seconds, hours, minutes, seconds)
        """
        if not deadline:
            return None
        
        now = datetime.utcnow()
        if now >= deadline:
            return {
                "expired": True,
                "total_seconds": 0,
                "hours": 0,
                "minutes": 0,
                "seconds": 0
            }
        
        remaining = deadline - now
        total_seconds = remaining.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        
        return {
            "expired": False,
            "total_seconds": total_seconds,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds
        }
