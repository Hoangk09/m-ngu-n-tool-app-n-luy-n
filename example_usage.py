"""
Example Usage Script - Quiz Auto-Solver Enhanced

This script demonstrates how to use the new quiz solving features
programmatically without running the full automation loop.

Includes examples of:
1. Creating quiz sessions
2. Saving individual answers
3. Querying quiz history
4. Using the answer database
5. Checking time expiry
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))

from quiz_saas.app.database import SessionLocal
from quiz_saas.app.services.answer_service import AnswerService


def example_1_create_and_save_quiz():
    """Example 1: Create a quiz session and save answers"""
    
    print("\n" + "="*70)
    print("EXAMPLE 1: Create Quiz Session & Save Answers")
    print("="*70 + "\n")
    
    db = SessionLocal()
    
    try:
        # Create a new quiz session
        print("Creating quiz session...")
        quiz_session = AnswerService.create_quiz_session(
            db=db,
            user_id=1,
            quiz_name="Sinh Học: Tuần Hoàn Động Vật",
            quiz_subject="11B5 - SINH HỌC",
            quiz_type="Kiểm tra 45 phút",
            total_questions=22,
            max_score=10.0,
            deadline=datetime.utcnow() + timedelta(hours=1),
            game_account_id=None
        )
        print(f"✓ Created session ID: {quiz_session.id}")
        print(f"  Quiz: {quiz_session.quiz_name}")
        print(f"  Subject: {quiz_session.quiz_subject}")
        print()
        
        # Save some answers
        print("Saving answers...")
        
        answers_data = [
            {"question": 1, "answer": "C", "points": 0.45, "max": 1.0},
            {"question": 2, "answer": "B", "points": 1.0, "max": 1.0},
            {"question": 3, "answer": "D", "points": 0.5, "max": 1.0},
            {"question": 4, "answer": "A", "points": 1.0, "max": 1.0},
            {"question": 5, "answer": "C", "points": 0.45, "max": 1.0},
        ]
        
        for data in answers_data:
            answer = AnswerService.save_answer(
                db=db,
                quiz_session_id=quiz_session.id,
                question_number=data["question"],
                correct_answer=data["answer"],
                student_answer=data["answer"],
                points_earned=data["points"],
                max_points=data["max"],
                question_content=f"Question {data['question']} content here...",
                explanation=f"This is the explanation for answer {data['answer']}"
            )
            print(f"  Q{data['question']}: {data['answer']} ({data['points']}/{data['max']}) ✓")
        
        print()
        
        # Finalize the quiz
        print("Finalizing quiz session...")
        session = AnswerService.finalize_quiz_session(db, quiz_session.id)
        print(f"✓ Quiz finalized")
        print(f"  Total Score: {session.total_score}/{session.max_score}")
        print(f"  Percentage: {session.percentage:.1f}%")
        print(f"  Status: {session.status}")
        
    finally:
        db.close()


def example_2_query_quiz_history():
    """Example 2: Query quiz history for a user"""
    
    print("\n" + "="*70)
    print("EXAMPLE 2: Query Quiz History")
    print("="*70 + "\n")
    
    db = SessionLocal()
    
    try:
        # Get quiz history
        sessions = AnswerService.get_quiz_history(db, user_id=1, limit=10)
        
        print(f"Quiz History for user 1 (last {len(sessions)} quizzes):")
        print()
        
        for i, session in enumerate(sessions, 1):
            print(f"{i}. {session.quiz_name}")
            print(f"   Subject: {session.quiz_subject}")
            print(f"   Score: {session.total_score}/{session.max_score} ({session.percentage:.1f}%)")
            print(f"   Status: {session.status}")
            print(f"   Date: {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
        
        if sessions:
            # Get detailed info on first quiz
            print("Detailed view of first quiz:")
            details = AnswerService.get_quiz_details(db, sessions[0].id)
            
            print(f"  Total Questions: {details['total_questions']}")
            print(f"  Correct Answers: {details['correct_count']}")
            print(f"  Duration: {details['duration_seconds'] // 60} minutes")
            print()
            
            print("  Answer breakdown:")
            for answer in details['answers'][:5]:  # Show first 5
                status = "✓" if answer['is_correct'] else "✗"
                print(f"    Q{answer['question_number']}: {status} {answer['student_answer']} "
                      f"({answer['points_earned']}/{answer['max_points']})")
            
            if len(details['answers']) > 5:
                print(f"    ... and {len(details['answers']) - 5} more")
        else:
            print("No quiz history found")
    
    finally:
        db.close()


def example_3_answer_database():
    """Example 3: Use collective answer database"""
    
    print("\n" + "="*70)
    print("EXAMPLE 3: Answer Database (Collective Statistics)")
    print("="*70 + "\n")
    
    db = SessionLocal()
    
    try:
        # Get answer database entries with high confidence
        results = AnswerService.get_answer_database(
            db, 
            question_content=None,
            min_confidence=0.7
        )
        
        print(f"Answer Database Statistics (confidence >= 0.7):")
        print(f"Total entries: {len(results)}")
        print()
        
        if results:
            print("High-confidence answers:")
            for i, entry in enumerate(results[:5], 1):
                print(f"{i}. Question: {entry.question_content[:50]}...")
                print(f"   Most Correct: {entry.most_correct_answer}")
                print(f"   Confidence: {entry.confidence:.1%}")
                print(f"   Verified: {entry.verified_count} times")
                total = (entry.answer_a_count + entry.answer_b_count + 
                        entry.answer_c_count + entry.answer_d_count)
                print(f"   Total Answers: {total}")
                print()
        else:
            print("No high-confidence answers yet")
            print("(Database builds up as more quizzes are completed)")
    
    finally:
        db.close()


def example_4_time_management():
    """Example 4: Time expiry checking"""
    
    print("\n" + "="*70)
    print("EXAMPLE 4: Time Management & Auto-Submission")
    print("="*70 + "\n")
    
    # Future deadline (1 hour from now)
    future_deadline = datetime.utcnow() + timedelta(hours=1)
    print(f"Future deadline: {future_deadline.strftime('%Y-%m-%d %H:%M:%S')}")
    
    expired = AnswerService.check_time_expiry(future_deadline)
    time_info = AnswerService.get_time_remaining(future_deadline)
    
    print(f"  Expired: {expired}")
    print(f"  Time remaining: {time_info['hours']}h {time_info['minutes']}m {time_info['seconds']}s")
    print(f"  Total seconds: {time_info['total_seconds']:.0f}")
    print()
    
    # Past deadline (1 hour ago)
    past_deadline = datetime.utcnow() - timedelta(hours=1)
    print(f"Past deadline: {past_deadline.strftime('%Y-%m-%d %H:%M:%S')}")
    
    expired = AnswerService.check_time_expiry(past_deadline)
    time_info = AnswerService.get_time_remaining(past_deadline)
    
    print(f"  Expired: {expired}")
    print(f"  Time remaining: {time_info['hours']}h {time_info['minutes']}m {time_info['seconds']}s")
    print()
    print("Auto-submission would trigger immediately for past deadlines")


def example_5_multi_quiz_analysis():
    """Example 5: Analyze performance across multiple quizzes"""
    
    print("\n" + "="*70)
    print("EXAMPLE 5: Multi-Quiz Performance Analysis")
    print("="*70 + "\n")
    
    db = SessionLocal()
    
    try:
        from sqlalchemy import func
        from quiz_saas.app.models import QuizSession, QuizAnswer
        
        # Get all quizzes for user
        quizzes = db.query(QuizSession).filter_by(user_id=1).all()
        
        if quizzes:
            print(f"Performance Summary for User 1:")
            print()
            
            total_score = sum(q.total_score for q in quizzes)
            total_max = sum(q.max_score for q in quizzes)
            avg_percentage = sum(q.percentage for q in quizzes) / len(quizzes)
            
            print(f"  Total Quizzes: {len(quizzes)}")
            print(f"  Overall Score: {total_score:.1f}/{total_max:.1f}")
            print(f"  Average Percentage: {avg_percentage:.1f}%")
            print()
            
            # By subject
            by_subject = db.query(
                QuizSession.quiz_subject,
                func.count(QuizSession.id).label('count'),
                func.avg(QuizSession.percentage).label('avg_pct')
            ).filter_by(user_id=1).group_by(QuizSession.quiz_subject).all()
            
            if by_subject:
                print("Performance by Subject:")
                for subject, count, avg_pct in by_subject:
                    print(f"  {subject}: {avg_pct:.1f}% ({count} quiz{'es' if count > 1 else ''})")
            
            print()
            
            # Question difficulty
            by_question = db.query(
                QuizAnswer.question_number,
                func.count(QuizAnswer.id).label('attempts'),
                func.avg(QuizAnswer.points_earned).label('avg_points')
            ).group_by(QuizAnswer.question_number).order_by(
                func.avg(QuizAnswer.points_earned)
            ).limit(5).all()
            
            if by_question:
                print("Hardest Questions (by average score):")
                for q_num, attempts, avg_pts in by_question:
                    print(f"  Q{q_num}: {avg_pts:.2f}/1.0 ({attempts} attempts)")
        else:
            print("No quizzes found for user 1")
            print("Run Example 1 first to create some quiz data")
    
    finally:
        db.close()


def menu():
    """Interactive menu for examples"""
    
    print("\n" + "="*70)
    print("Quiz Auto-Solver - Example Usage Menu")
    print("="*70)
    print()
    print("1. Create Quiz Session & Save Answers")
    print("2. Query Quiz History")
    print("3. Answer Database (Collective Statistics)")
    print("4. Time Management & Auto-Submission")
    print("5. Multi-Quiz Analysis")
    print("6. Run All Examples")
    print("0. Exit")
    print()
    
    choice = input("Select example (0-6): ").strip()
    
    examples = {
        '1': example_1_create_and_save_quiz,
        '2': example_2_query_quiz_history,
        '3': example_3_answer_database,
        '4': example_4_time_management,
        '5': example_5_multi_quiz_analysis,
        '6': lambda: [
            example_1_create_and_save_quiz(),
            example_2_query_quiz_history(),
            example_3_answer_database(),
            example_4_time_management(),
            example_5_multi_quiz_analysis()
        ]
    }
    
    if choice == '0':
        print("Exiting...")
        return False
    
    if choice in examples:
        examples[choice]()
        return True
    else:
        print("Invalid choice")
        return True


if __name__ == "__main__":
    print()
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  Quiz Auto-Solver - Enhanced Features Examples".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    # Check if database is initialized
    try:
        db = SessionLocal()
        from quiz_saas.app.models import QuizSession
        db.query(QuizSession).first()
        db.close()
    except Exception as e:
        print()
        print("⚠️  Database not initialized!")
        print("Run: python init_database.py --init")
        print()
        sys.exit(1)
    
    # Show examples in interactive menu
    if len(sys.argv) > 1:
        # Command line argument mode
        example_num = sys.argv[1]
        
        examples = {
            '1': example_1_create_and_save_quiz,
            '2': example_2_query_quiz_history,
            '3': example_3_answer_database,
            '4': example_4_time_management,
            '5': example_5_multi_quiz_analysis,
            'all': lambda: [
                example_1_create_and_save_quiz(),
                example_2_query_quiz_history(),
                example_3_answer_database(),
                example_4_time_management(),
                example_5_multi_quiz_analysis()
            ]
        }
        
        if example_num in examples:
            examples[example_num]()
        else:
            print(f"Unknown example: {example_num}")
            print("Usage: python example_usage.py [1-5|all]")
    else:
        # Interactive menu mode
        while True:
            try:
                if not menu():
                    break
            except KeyboardInterrupt:
                print("\n\nExiting...")
                break
            except Exception as e:
                print(f"\n✗ Error: {e}")
                import traceback
                traceback.print_exc()
