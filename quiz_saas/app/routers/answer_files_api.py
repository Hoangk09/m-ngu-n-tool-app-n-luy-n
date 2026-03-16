"""
Backend API Endpoints for Answer Files
Adds to quiz_saas/app/routers/api.py
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import hashlib
import json
from typing import Dict, Optional, List

router = APIRouter(prefix="/api", tags=["answer-files"])


# ============================================
# MODELS
# ============================================

class AnswerFileRequest(BaseModel):
    quiz_name: str
    quiz_hash: Optional[str] = None


class AnswerFileSaveRequest(BaseModel):
    quiz_name: str
    quiz_hash: Optional[str] = None
    answers: Dict[int, str]  # {1: "A", 2: "B", ...}
    timestamp: str
    quiz_details: Optional[Dict] = None


class AnswerFileResponse(BaseModel):
    success: bool
    answers: Optional[Dict[int, str]] = None
    message: str


# ============================================
# ENDPOINTS
# ============================================

@router.post("/get-answer-file", response_model=AnswerFileResponse)
async def get_answer_file(request: AnswerFileRequest):
    """
    Get answer file for a quiz from backend
    
    Request:
    {
        "quiz_name": "Kiểm tra 45 phút - SINH HỌC",
        "quiz_hash": "md5_hash_of_name"
    }
    
    Response:
    {
        "success": true,
        "answers": {
            "1": "A",
            "2": "C",
            "3": "B",
            ...
        }
    }
    """
    try:
        from sqlalchemy.orm import Session
        from quiz_saas.app.database import SessionLocal
        
        db: Session = SessionLocal()
        
        # Try to find answer file in database
        # Assuming AnswerDatabase model exists
        from quiz_saas.app.models import AnswerDatabase
        
        # Search by name or hash
        answer_record = db.query(AnswerDatabase).filter(
            (AnswerDatabase.quiz_name == request.quiz_name) |
            (AnswerDatabase.quiz_hash == request.quiz_hash)
        ).first()
        
        if answer_record and answer_record.answer_file_json:
            try:
                answers = json.loads(answer_record.answer_file_json)
                return AnswerFileResponse(
                    success=True,
                    answers=answers,
                    message=f"Tìm thấy đáp án ({len(answers)} câu)"
                )
            except:
                pass
        
        return AnswerFileResponse(
            success=False,
            answers=None,
            message="Chưa có đáp án cho bài này"
        )
    
    except Exception as e:
        return AnswerFileResponse(
            success=False,
            answers=None,
            message=f"Lỗi: {str(e)}"
        )
    finally:
        if 'db' in locals():
            db.close()


@router.post("/save-answer-file")
async def save_answer_file(request: AnswerFileSaveRequest):
    """
    Save answer file to backend after solving
    
    Request:
    {
        "quiz_name": "Kiểm tra 45 phút - SINH HỌC",
        "answers": {
            "1": "A",
            "2": "C",
            ...
        },
        "timestamp": "2025-12-11T10:30:00",
        "quiz_details": {
            "total_questions": 40,
            "solved_time": "2025-12-11T10:50:00"
        }
    }
    """
    try:
        from sqlalchemy.orm import Session
        from quiz_saas.app.database import SessionLocal
        from quiz_saas.app.models import AnswerDatabase
        
        db: Session = SessionLocal()
        
        # Generate hash if not provided
        quiz_hash = request.quiz_hash or hashlib.md5(
            request.quiz_name.encode()
        ).hexdigest()
        
        # Check if already exists
        existing = db.query(AnswerDatabase).filter(
            (AnswerDatabase.quiz_name == request.quiz_name) |
            (AnswerDatabase.quiz_hash == quiz_hash)
        ).first()
        
        answer_json = json.dumps(request.answers)
        
        if existing:
            # Update existing
            existing.answer_file_json = answer_json
            existing.updated_at = datetime.now()
            existing.times_used += 1
        else:
            # Create new
            new_record = AnswerDatabase(
                quiz_name=request.quiz_name,
                quiz_hash=quiz_hash,
                answer_file_json=answer_json,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                times_used=1,
                quiz_details=json.dumps(request.quiz_details or {})
            )
            db.add(new_record)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Đã lưu đáp án ({len(request.answers)} câu)",
            "hash": quiz_hash
        }
    
    except Exception as e:
        db.rollback() if 'db' in locals() else None
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'db' in locals():
            db.close()


@router.get("/answer-files/list")
async def list_answer_files(skip: int = 0, limit: int = 50):
    """Get list of saved answer files"""
    try:
        from sqlalchemy.orm import Session
        from quiz_saas.app.database import SessionLocal
        from quiz_saas.app.models import AnswerDatabase
        
        db: Session = SessionLocal()
        
        records = db.query(AnswerDatabase).offset(skip).limit(limit).all()
        
        return {
            "success": True,
            "count": len(records),
            "files": [
                {
                    "quiz_name": r.quiz_name,
                    "quiz_hash": r.quiz_hash,
                    "num_answers": len(json.loads(r.answer_file_json or "{}")),
                    "times_used": r.times_used,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None
                }
                for r in records
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'db' in locals():
            db.close()


@router.delete("/answer-files/{quiz_hash}")
async def delete_answer_file(quiz_hash: str):
    """Delete an answer file"""
    try:
        from sqlalchemy.orm import Session
        from quiz_saas.app.database import SessionLocal
        from quiz_saas.app.models import AnswerDatabase
        
        db: Session = SessionLocal()
        
        record = db.query(AnswerDatabase).filter(
            AnswerDatabase.quiz_hash == quiz_hash
        ).first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Không tìm thấy")
        
        db.delete(record)
        db.commit()
        
        return {"success": True, "message": "Đã xóa"}
    except Exception as e:
        db.rollback() if 'db' in locals() else None
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'db' in locals():
            db.close()


@router.post("/answer-files/search")
async def search_answer_files(query: str, limit: int = 10):
    """Search answer files by name"""
    try:
        from sqlalchemy.orm import Session
        from quiz_saas.app.database import SessionLocal
        from quiz_saas.app.models import AnswerDatabase
        
        db: Session = SessionLocal()
        
        records = db.query(AnswerDatabase).filter(
            AnswerDatabase.quiz_name.ilike(f"%{query}%")
        ).limit(limit).all()
        
        return {
            "success": True,
            "results": [
                {
                    "quiz_name": r.quiz_name,
                    "quiz_hash": r.quiz_hash,
                    "num_answers": len(json.loads(r.answer_file_json or "{}")),
                    "times_used": r.times_used
                }
                for r in records
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'db' in locals():
            db.close()
