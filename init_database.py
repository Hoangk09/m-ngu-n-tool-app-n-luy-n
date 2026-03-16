"""
Database Initialization Script

This script initializes the database with all required tables for the enhanced 
quiz solver system, including:
- QuizSession (quiz metadata and results)
- QuizAnswer (individual answers per question)
- AnswerDatabase (collective answer statistics)

Run this once to set up the database for the new features.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from quiz_saas.app.database import engine, Base, SessionLocal
from quiz_saas.app import models


def init_database():
    """Initialize all database tables"""
    print("Initializing database...")
    print("-" * 60)
    
    try:
        # Create all tables
        print("Creating tables...")
        Base.metadata.create_all(bind=engine)
        
        print("✓ Tables created successfully")
        print()
        
        # List created tables
        print("Tables created:")
        print("-" * 60)
        
        tables_info = {
            "users": "User accounts",
            "game_accounts": "Game account credentials",
            "transactions": "Payment transactions",
            "quiz_sessions": "Quiz sessions with scores [NEW]",
            "quiz_answers": "Individual answers per question [NEW]",
            "answer_database": "Collective answer statistics [NEW]"
        }
        
        for table_name, description in tables_info.items():
            print(f"  ✓ {table_name:20} - {description}")
        
        print()
        print("=" * 60)
        print("Database initialization completed successfully!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Verify all tables exist in database")
        print("2. Update quiz_solver_enhanced.py with correct URLs")
        print("3. Start backend server: python quiz_saas/app/main.py")
        print("4. Run automation: python quiz_solver_enhanced.py")
        print()
        
        return True
    
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_database():
    """Verify database tables exist and show stats"""
    print("\nVerifying database tables...")
    print("-" * 60)
    
    try:
        db = SessionLocal()
        
        # Check if tables exist
        inspector = __import__('sqlalchemy').inspect(engine)
        tables = inspector.get_table_names()
        
        new_tables = ['quiz_sessions', 'quiz_answers', 'answer_database']
        
        print(f"Total tables in database: {len(tables)}")
        print()
        
        for table in new_tables:
            if table in tables:
                # Get row count
                if table == 'quiz_sessions':
                    count = db.query(models.QuizSession).count()
                    print(f"✓ {table:20} - {count} records")
                elif table == 'quiz_answers':
                    count = db.query(models.QuizAnswer).count()
                    print(f"✓ {table:20} - {count} records")
                elif table == 'answer_database':
                    count = db.query(models.AnswerDatabase).count()
                    print(f"✓ {table:20} - {count} records")
            else:
                print(f"✗ {table:20} - NOT FOUND")
        
        db.close()
        return True
    
    except Exception as e:
        print(f"✗ Verification failed: {e}")
        return False


def show_schema():
    """Show database schema information"""
    print("\nDatabase Schema:")
    print("-" * 60)
    
    print("""
QUIZ_SESSIONS table:
  - id: Integer (PK)
  - user_id: Integer (FK)
  - game_account_id: Integer (FK)
  - quiz_name: String
  - quiz_subject: String
  - quiz_type: String
  - total_questions: Integer
  - start_time: DateTime
  - end_time: DateTime
  - deadline: DateTime
  - total_score: Float
  - max_score: Float
  - percentage: Float
  - status: String (in_progress, submitted, auto_submitted, failed)
  - auto_submitted: Boolean

QUIZ_ANSWERS table:
  - id: Integer (PK)
  - quiz_session_id: Integer (FK)
  - question_number: Integer
  - question_content: Text
  - correct_answer: String (A/B/C/D)
  - student_answer: String (A/B/C/D)
  - is_correct: Boolean
  - points_earned: Float
  - max_points: Float
  - answer_timestamp: DateTime
  - explanation: Text

ANSWER_DATABASE table:
  - id: Integer (PK)
  - question_content_hash: String (UNIQUE)
  - question_content: Text
  - answer_a_count: Integer
  - answer_b_count: Integer
  - answer_c_count: Integer
  - answer_d_count: Integer
  - most_common_answer: String (A/B/C/D)
  - most_correct_answer: String (A/B/C/D)
  - confidence: Float (0-1)
  - first_seen: DateTime
  - last_updated: DateTime
  - verified_count: Integer
    """)


def reset_database(confirm=True):
    """Drop all tables and reinitialize (WARNING: Destructive!)"""
    if confirm:
        response = input("WARNING: This will DELETE all data! Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Operation cancelled")
            return False
    
    print("Dropping all tables...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("✓ All tables dropped")
        
        print("Recreating tables...")
        Base.metadata.create_all(bind=engine)
        print("✓ Tables recreated")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Database initialization for Quiz Auto-Solver"
    )
    parser.add_argument(
        '--init', 
        action='store_true', 
        help='Initialize database with new tables'
    )
    parser.add_argument(
        '--verify', 
        action='store_true', 
        help='Verify database tables and show statistics'
    )
    parser.add_argument(
        '--schema', 
        action='store_true', 
        help='Show database schema'
    )
    parser.add_argument(
        '--reset', 
        action='store_true', 
        help='Reset database (WARNING: destructive!)'
    )
    
    args = parser.parse_args()
    
    # Default action if no args
    if not any([args.init, args.verify, args.schema, args.reset]):
        args.init = True
        args.verify = True
        args.schema = True
    
    print()
    print("=" * 60)
    print("Quiz Auto-Solver Database Initialization")
    print("=" * 60)
    print()
    
    if args.init:
        init_database()
    
    if args.verify:
        verify_database()
    
    if args.schema:
        show_schema()
    
    if args.reset:
        if reset_database(confirm=True):
            verify_database()
    
    print()
