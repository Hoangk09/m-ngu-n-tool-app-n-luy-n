"""
Database Migration - Add AnswerDatabase Model
Run this once to add the answer file storage table
"""

from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

# Import existing models
import sys
sys.path.insert(0, 'quiz_saas')

from app.database import Base, engine
from app.models import AnswerDatabase

def migrate_add_answer_database():
    """Add AnswerDatabase table if it doesn't exist"""
    
    print("🔄 Starting database migration...")
    
    # Create table if doesn't exist
    try:
        Base.metadata.create_all(engine)
        print("✅ Database tables created/updated")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False
    
    # Verify table exists
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'answer_database' in tables:
            print("✅ AnswerDatabase table exists")
            
            # Check columns
            columns = [col['name'] for col in inspector.get_columns('answer_database')]
            required_cols = [
                'id', 'quiz_name', 'quiz_hash', 'answer_file_json',
                'times_used', 'created_at', 'updated_at', 'quiz_details'
            ]
            
            for col in required_cols:
                if col in columns:
                    print(f"  ✓ Column '{col}' exists")
                else:
                    print(f"  ✗ Column '{col}' MISSING")
            
            return True
        else:
            print("❌ AnswerDatabase table not found")
            return False
    except Exception as e:
        print(f"❌ Error verifying table: {e}")
        return False


def verify_and_add_model():
    """Verify AnswerDatabase model and create sample data"""
    
    print("\n🔍 Verifying AnswerDatabase model...")
    
    from app.database import SessionLocal
    
    db = SessionLocal()
    
    try:
        # Try to query existing records
        count = db.query(AnswerDatabase).count()
        print(f"✅ AnswerDatabase model working - {count} existing records")
        
        # Show sample record if exists
        sample = db.query(AnswerDatabase).first()
        if sample:
            print(f"\nSample Record:")
            print(f"  Quiz: {sample.quiz_name}")
            print(f"  Hash: {sample.quiz_hash}")
            print(f"  Answers: {len(json.loads(sample.answer_file_json or '{}'))} questions")
            print(f"  Times Used: {sample.times_used}")
            print(f"  Created: {sample.created_at}")
        
        return True
    except Exception as e:
        print(f"❌ Error with model: {e}")
        return False
    finally:
        db.close()


def test_answer_api():
    """Test if API endpoints work"""
    
    print("\n🧪 Testing API endpoints...")
    
    try:
        import requests
        
        base_url = "http://localhost:8000/api"
        
        # Test 1: List answer files
        try:
            resp = requests.get(f"{base_url}/answer-files/list?limit=5", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ GET /answer-files/list - {data.get('count', 0)} files")
            else:
                print(f"❌ GET /answer-files/list - Status {resp.status_code}")
        except requests.exceptions.ConnectionError:
            print("⚠️ Cannot connect to backend - not running?")
        
        # Test 2: Search
        try:
            resp = requests.post(
                f"{base_url}/answer-files/search",
                json={"query": "SINH", "limit": 5},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ POST /answer-files/search - {len(data.get('results', []))} matches")
        except:
            pass
        
    except ImportError:
        print("⚠️ requests library not installed - skipping API tests")


def create_sample_answers():
    """Create sample answer data for testing"""
    
    print("\n📝 Creating sample answer data...")
    
    from app.database import SessionLocal
    
    db = SessionLocal()
    
    try:
        # Check if sample already exists
        existing = db.query(AnswerDatabase).filter(
            AnswerDatabase.quiz_name.like("%SINH HỌC%")
        ).first()
        
        if existing:
            print(f"✅ Sample data already exists: {existing.quiz_name}")
            return
        
        # Create sample
        sample_answers = {
            str(i): ["A", "B", "C", "D"][i % 4]
            for i in range(1, 41)
        }
        
        sample = AnswerDatabase(
            quiz_name="Kiểm tra 45 phút - SINH HỌC",
            quiz_hash="abc123def456",
            answer_file_json=json.dumps(sample_answers),
            times_used=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            quiz_details=json.dumps({
                "total_questions": 40,
                "subject": "SINH HỌC",
                "time_limit": 45,
                "source": "Sample Data"
            })
        )
        
        db.add(sample)
        db.commit()
        
        print(f"✅ Created sample: {sample.quiz_name}")
        print(f"   Answers: {len(sample_answers)} questions")
        print(f"   Hash: {sample.quiz_hash}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating sample: {e}")
    finally:
        db.close()


def show_schema():
    """Display database schema"""
    
    print("\n📋 Database Schema (answer_database table):")
    print("""
    Column Name          | Type         | Description
    ─────────────────────┼──────────────┼──────────────────────────
    id                   | INTEGER      | Primary Key
    quiz_name            | VARCHAR      | Quiz name (indexed)
    quiz_hash            | VARCHAR      | MD5 hash of name (indexed)
    answer_file_json     | JSON         | Answers in JSON format
    times_used           | INTEGER      | How many times used
    created_at           | DATETIME     | Creation timestamp
    updated_at           | DATETIME     | Last update timestamp
    quiz_details         | JSON         | Additional metadata
    ─────────────────────┴──────────────┴──────────────────────────
    
    Indexes:
    - quiz_name (for search)
    - quiz_hash (for lookup)
    
    Example Data:
    {
      "quiz_name": "Kiểm tra 45 phút - SINH HỌC",
      "quiz_hash": "md5_hash",
      "answer_file_json": "{\\"1\\": \\"A\\", \\"2\\": \\"C\\", ...}",
      "times_used": 5,
      "created_at": "2025-12-01T10:30:00",
      "updated_at": "2025-12-11T15:45:00",
      "quiz_details": "{\\"total_questions\\": 40, ...}"
    }
    """)


def main():
    """Run all migration checks"""
    
    print("=" * 60)
    print("DATABASE MIGRATION - Answer Storage")
    print("=" * 60)
    
    # Step 1: Create tables
    if not migrate_add_answer_database():
        print("\n❌ Migration failed at table creation")
        return False
    
    # Step 2: Verify model
    if not verify_and_add_model():
        print("\n⚠️ Model verification failed, but continuing...")
    
    # Step 3: Create sample data
    create_sample_answers()
    
    # Step 4: Show schema
    show_schema()
    
    # Step 5: Test API
    test_answer_api()
    
    print("\n" + "=" * 60)
    print("✅ Migration completed successfully!")
    print("=" * 60)
    
    print("""
Next Steps:
1. Ensure quiz_saas backend is running:
   cd quiz_saas
   uvicorn app.main:app --reload --port 8000

2. Update quiz_saas/app/main.py to include router:
   from quiz_saas.app.routers import answer_files_api
   app.include_router(answer_files_api.router)

3. Restart backend and verify endpoints:
   - Test: curl http://localhost:8000/api/answer-files/list

4. Configure quiz_solver_app.py:
   - Set Backend URL: http://localhost:8000
   - Enable "📁 Kiểm tra backend"
   - Enable "💾 Lưu đáp án" (optional)

5. Run the quiz solver as usual!
    """)
    
    return True


if __name__ == "__main__":
    import sys
    sys.path.insert(0, 'quiz_saas')
    
    success = main()
    sys.exit(0 if success else 1)
