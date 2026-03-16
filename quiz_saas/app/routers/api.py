from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from ..services.answer_service import AnswerService
from pydantic import BaseModel
from typing import List, Optional


router = APIRouter()


# ==========================================
# PYDANTIC SCHEMAS
# ==========================================

class QuizAnswerCreate(BaseModel):
    """Schema for saving a single answer"""
    question_number: int
    correct_answer: str
    student_answer: Optional[str] = None
    points_earned: float = 0.0
    max_points: float = 1.0
    question_content: Optional[str] = None
    explanation: Optional[str] = None


class QuizSessionCreate(BaseModel):
    """Schema for creating a quiz session"""
    user_id: int
    quiz_name: str
    quiz_subject: str
    quiz_type: str
    total_questions: int
    max_score: Optional[float] = None
    deadline: Optional[datetime] = None
    game_account_id: Optional[int] = None


class AnswerDatabaseResponse(BaseModel):
    """Response schema for answer database entries"""
    question_content: str
    most_common_answer: Optional[str]
    most_correct_answer: Optional[str]
    confidence: float
    verified_count: int
    
    class Config:
        from_attributes = True


class QuizSessionResponse(BaseModel):
    """Response schema for quiz session"""
    id: int
    quiz_name: str
    quiz_subject: str
    total_questions: int
    total_score: float
    max_score: float
    percentage: Optional[float]
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    
    class Config:
        from_attributes = True


# ==========================================
# API ROUTES
# ==========================================

@router.get("/api")
def api_root():
    return {"message": "Quiz Answer API", "version": "1.0"}


# ==========================================
# QUIZ SESSION MANAGEMENT
# ==========================================

@router.post("/api/quiz-session/create")
def create_quiz_session(
    session_data: QuizSessionCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new quiz session
    
    Returns:
        Created QuizSession with ID for use in subsequent answer saves
    """
    try:
        quiz_session = AnswerService.create_quiz_session(
            db=db,
            user_id=session_data.user_id,
            quiz_name=session_data.quiz_name,
            quiz_subject=session_data.quiz_subject,
            quiz_type=session_data.quiz_type,
            total_questions=session_data.total_questions,
            max_score=session_data.max_score,
            deadline=session_data.deadline,
            game_account_id=session_data.game_account_id
        )
        return {
            "success": True,
            "quiz_session_id": quiz_session.id,
            "message": f"Quiz session created for '{quiz_session.quiz_name}'"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# ANSWER SAVING
# ==========================================

@router.post("/api/quiz-answers")
def save_answer(
    quiz_session_id: int,
    answer_data: QuizAnswerCreate,
    db: Session = Depends(get_db)
):
    """
    Save a single answer to the database
    Called after each question is answered
    
    Args:
        quiz_session_id: ID of the current quiz session
        answer_data: The answer information to save
    
    Returns:
        Success confirmation with answer ID
    """
    try:
        answer = AnswerService.save_answer(
            db=db,
            quiz_session_id=quiz_session_id,
            question_number=answer_data.question_number,
            correct_answer=answer_data.correct_answer,
            student_answer=answer_data.student_answer,
            points_earned=answer_data.points_earned,
            max_points=answer_data.max_points,
            question_content=answer_data.question_content,
            explanation=answer_data.explanation
        )
        return {
            "success": True,
            "answer_id": answer.id,
            "is_correct": answer.is_correct,
            "points_earned": answer.points_earned
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/quiz-submit")
def submit_quiz(
    quiz_session_id: int,
    auto_submitted: bool = False,
    db: Session = Depends(get_db)
):
    """
    Finalize and submit a quiz session
    Called when quiz is completed or time expires
    
    Args:
        quiz_session_id: ID of the quiz session to finalize
        auto_submitted: Whether this was auto-submitted due to time expiry
    
    Returns:
        Final quiz results with total score and percentage
    """
    try:
        session = AnswerService.finalize_quiz_session(
            db=db,
            quiz_session_id=quiz_session_id,
            auto_submitted=auto_submitted
        )
        return {
            "success": True,
            "quiz_session_id": session.id,
            "quiz_name": session.quiz_name,
            "total_score": session.total_score,
            "max_score": session.max_score,
            "percentage": session.percentage,
            "status": session.status,
            "auto_submitted": session.auto_submitted,
            "duration_seconds": (
                (session.end_time - session.start_time).total_seconds()
                if session.end_time else None
            )
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# QUIZ HISTORY & DETAILS
# ==========================================

@router.get("/api/quiz-history/{user_id}")
def get_quiz_history(
    user_id: int,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Get quiz history for a user
    
    Args:
        user_id: ID of the user
        limit: Maximum number of records to return
    
    Returns:
        List of quiz sessions
    """
    try:
        sessions = AnswerService.get_quiz_history(db, user_id, limit)
        return {
            "success": True,
            "count": len(sessions),
            "sessions": [
                {
                    "id": s.id,
                    "quiz_name": s.quiz_name,
                    "quiz_subject": s.quiz_subject,
                    "total_score": s.total_score,
                    "max_score": s.max_score,
                    "percentage": s.percentage,
                    "status": s.status,
                    "start_time": s.start_time
                }
                for s in sessions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/quiz-details/{quiz_session_id}")
def get_quiz_details(
    quiz_session_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a quiz session
    Includes all answers with correct/incorrect status
    
    Args:
        quiz_session_id: ID of the quiz session
    
    Returns:
        Quiz details including all answers and scoring
    """
    try:
        details = AnswerService.get_quiz_details(db, quiz_session_id)
        if not details:
            raise HTTPException(status_code=404, detail="Quiz session not found")
        
        return {
            "success": True,
            "session": {
                "id": details["session"].id,
                "quiz_name": details["session"].quiz_name,
                "quiz_subject": details["session"].quiz_subject,
                "total_questions": details["total_questions"],
                "correct_count": details["correct_count"],
                "total_score": details["total_score"],
                "max_score": details["max_score"],
                "percentage": details["percentage"],
                "status": details["session"].status
            },
            "answers": [
                {
                    "question_number": a.question_number,
                    "correct_answer": a.correct_answer,
                    "student_answer": a.student_answer,
                    "is_correct": a.is_correct,
                    "points_earned": a.points_earned,
                    "max_points": a.max_points,
                    "explanation": a.explanation
                }
                for a in details["answers"]
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# ANSWER DATABASE / SUGGESTIONS
# ==========================================

@router.get("/api/answer-database")
def get_answer_suggestions(
    question_content: Optional[str] = None,
    min_confidence: float = 0.5,
    db: Session = Depends(get_db)
):
    """
    Get answer suggestions from collective database
    Used to improve answer accuracy by using previously solved questions
    
    Args:
        question_content: Optional question to search for
        min_confidence: Minimum confidence threshold (0-1)
    
    Returns:
        List of answer suggestions with confidence scores
    """
    try:
        results = AnswerService.get_answer_database(
            db, question_content, min_confidence
        )
        return {
            "success": True,
            "count": len(results),
            "suggestions": [
                {
                    "most_common_answer": r.most_common_answer,
                    "most_correct_answer": r.most_correct_answer,
                    "confidence": r.confidence,
                    "verified_count": r.verified_count,
                    "total_answers": (
                        r.answer_a_count + r.answer_b_count + 
                        r.answer_c_count + r.answer_d_count
                    )
                }
                for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# TIME MANAGEMENT / AUTO-SUBMISSION
# ==========================================

@router.post("/api/check-time-expiry")
def check_time_expiry(
    deadline: datetime,
    db: Session = Depends(get_db)
):
    """
    Check if quiz deadline has passed
    Used to determine if auto-submission should trigger
    
    Args:
        deadline: Quiz deadline datetime
    
    Returns:
        Expiry status and time remaining
    """
    try:
        expired = AnswerService.check_time_expiry(deadline)
        time_info = AnswerService.get_time_remaining(deadline)
        
        return {
            "success": True,
            "expired": expired,
            "time_remaining": time_info
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/time-remaining")
def get_time_remaining(
    deadline: datetime,
    db: Session = Depends(get_db)
):
    """
    Get detailed time remaining until deadline
    
    Args:
        deadline: Quiz deadline datetime
    
    Returns:
        Time remaining in hours, minutes, seconds
    """
    try:
        time_info = AnswerService.get_time_remaining(deadline)
        
        return {
            "success": True,
            "time_remaining": time_info
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
