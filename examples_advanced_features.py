"""
Advanced Quiz Solving - Example Usage
Demonstrates all features of quiz_logic_advanced.py
"""

import time
from quiz_logic_advanced import QuizSolver, AnswerFileManager

# Example 1: Check if answer file exists
print("=" * 60)
print("EXAMPLE 1: Check for Answer File")
print("=" * 60)

answer_manager = AnswerFileManager("http://localhost:8000")

quiz_name = "Kiểm tra 45 phút - SINH HỌC"
answer_file = answer_manager.get_answer_file(quiz_name)

if answer_file:
    print(f"✅ Found answer file with {len(answer_file)} answers:")
    for q_num, answer in list(answer_file.items())[:5]:
        print(f"   Q{q_num}: {answer}")
    if len(answer_file) > 5:
        print(f"   ... and {len(answer_file) - 5} more")
else:
    print(f"❌ No answer file found for '{quiz_name}'")

# Example 2: Save answers to backend
print("\n" + "=" * 60)
print("EXAMPLE 2: Save Answer File to Backend")
print("=" * 60)

answers_to_save = {
    1: "A",
    2: "B",
    3: "C",
    4: "D",
    5: "A",
    # ... more answers
}

success = answer_manager.save_answers_to_backend(
    quiz_name,
    answers_to_save,
    {
        "total_questions": 40,
        "subject": "SINH HỌC",
        "time_limit": 45,
    }
)

if success:
    print(f"✅ Successfully saved {len(answers_to_save)} answers")
    print(f"   Quiz: {quiz_name}")
    print(f"   Total answers: {len(answers_to_save)}")
else:
    print("❌ Failed to save answers")

# Example 3: Answer file workflow
print("\n" + "=" * 60)
print("EXAMPLE 3: Complete Quiz Solving Workflow")
print("=" * 60)

config = {
    "api_key": "your-gemini-api-key",
    "backend_url": "http://localhost:8000",
    "quiz_time": 45,
    "check_answer_files": True,
    "save_answers": False,
    "continue_on_timeout": True,
}

def my_log_callback(message):
    """Custom logging function"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

# This would be called with a real Selenium driver:
# solver = QuizSolver(driver, config, my_log_callback)
# solver.start_quiz(quiz_time=45)

print("✅ Workflow configuration ready:")
print(f"   API Key: {config['api_key'][:10]}...")
print(f"   Backend: {config['backend_url']}")
print(f"   Time Limit: {config['quiz_time']} minutes")
print(f"   Check Files: {'Yes' if config['check_answer_files'] else 'No'}")
print(f"   Save Answers: {'Yes' if config['save_answers'] else 'No'}")
print(f"   Continue on Timeout: {'Yes' if config['continue_on_timeout'] else 'No'}")

# Example 4: Integration with main quiz_logic_advanced
print("\n" + "=" * 60)
print("EXAMPLE 4: Using solve_quiz() Function")
print("=" * 60)

print("""
To use the complete workflow:

from quiz_logic_advanced import solve_quiz

config = {
    "api_key": "your-api-key",
    "backend_url": "http://localhost:8000",
    "quiz_time": 45,
    "check_answer_files": True,
    "save_answers": True,
    "continue_on_timeout": False,
}

# After logging in and navigating to quiz
success = solve_quiz(driver, config, log_callback=print)

if success:
    print("✅ Quiz completed successfully!")
    # Check backend for saved answers
    # or use answer file next time
""")

# Example 5: Manual answer management
print("\n" + "=" * 60)
print("EXAMPLE 5: Manual Answer File Management")
print("=" * 60)

# List all saved answer files
print("""
List all answer files:
    GET /api/answer-files/list

Search for specific quiz:
    POST /api/answer-files/search
    {"query": "SINH HỌC"}

Delete old answer file:
    DELETE /api/answer-files/{quiz_hash}

Get specific answer file:
    POST /api/get-answer-file
    {"quiz_name": "..."}
""")

# Example 6: Backend integration
print("\n" + "=" * 60)
print("EXAMPLE 6: Backend Setup")
print("=" * 60)

print("""
1. Ensure quiz_saas backend is running:
   cd quiz_saas
   uvicorn app.main:app --reload --port 8000

2. Check AnswerDatabase model in quiz_saas/app/models.py:
   - quiz_name: varchar
   - quiz_hash: varchar (MD5)
   - answer_file_json: JSON
   - times_used: integer
   - created_at, updated_at: datetime

3. API endpoints are in quiz_saas/app/routers/answer_files_api.py:
   - GET /api/get-answer-file
   - POST /api/save-answer-file
   - GET /api/answer-files/list
   - POST /api/answer-files/search
   - DELETE /api/answer-files/{quiz_hash}

4. Register router in quiz_saas/app/main.py:
   from quiz_saas.app.routers import answer_files_api
   app.include_router(answer_files_api.router)
""")

# Example 7: Usage statistics
print("\n" + "=" * 60)
print("EXAMPLE 7: Performance & Statistics")
print("=" * 60)

# Simulate usage stats
example_stats = {
    "quiz_name": "Kiểm tra 45 phút - SINH HỌC",
    "times_used": 12,
    "total_answers": 40,
    "date_created": "2025-12-01",
    "date_updated": "2025-12-11",
    "file_size_bytes": 512,
    "avg_time_per_run": 3.5,  # minutes (with file, no Gemini)
}

print(f"""
Answer File Statistics:
├─ Quiz: {example_stats['quiz_name']}
├─ Times Used: {example_stats['times_used']}
├─ Total Answers: {example_stats['total_answers']}
├─ Created: {example_stats['date_created']}
├─ Updated: {example_stats['date_updated']}
├─ File Size: {example_stats['file_size_bytes']} bytes
└─ Avg Time/Run: {example_stats['avg_time_per_run']} minutes

Time Saved:
├─ Per run: ~1-2 minutes (vs Gemini)
├─ Total saved: {(example_stats['times_used'] - 1) * 1.5} minutes
└─ Cost saved: ~$0.004/run = ${(example_stats['times_used'] - 1) * 0.004:.2f} total

Performance Boost:
├─ Using file: 3.5 min average
└─ Using Gemini: 5-7 min average
└─ Speedup: ~40% faster with file
""")

# Example 8: Error handling
print("\n" + "=" * 60)
print("EXAMPLE 8: Error Handling")
print("=" * 60)

print("""
Common Issues & Solutions:

1. Backend Connection Failed
   Error: "Cannot connect to backend"
   Solution:
   - Check backend URL is correct
   - Ensure backend is running
   - Check firewall/network settings
   - Set check_answer_files=False to use Gemini only

2. Answer File Not Found
   Error: "No answer file for quiz"
   Solution:
   - Quiz name must match exactly
   - Run with save_answers=True to create file
   - Wait for next run to use the file

3. Invalid Answer Format
   Error: "Answer JSON corrupted"
   Solution:
   - Manually delete from backend
   - Re-run quiz with save_answers=True
   - Verify backend database

4. API Rate Limit
   Error: "Too many requests"
   Solution:
   - Use answer files to reduce API calls
   - Space out requests by 2-3 seconds
   - Check Gemini API quota
""")

# Example 9: Advanced configuration
print("\n" + "=" * 60)
print("EXAMPLE 9: Advanced Configuration")
print("=" * 60)

print("""
Config Options & Their Effects:

check_answer_files: True/False
├─ True: Check backend before each quiz (recommended)
└─ False: Skip backend, use Gemini every time

save_answers: True/False
├─ True: Save answers to backend after quiz
└─ False: Don't save (use existing files only)

continue_on_timeout: True/False
├─ True: Click "Kết Thúc" immediately (safe, fast)
└─ False: Continue checking answers until done

backend_url: string
├─ "http://localhost:8000" (local development)
├─ "https://api.yourdomain.com" (production)
└─ "http://docker-container:8000" (Docker)

api_key: string
├─ Your Gemini API key
├─ Get from: https://ai.google.dev
└─ Keep secret & rotate regularly

quiz_time: integer (minutes)
├─ 10-90 minutes recommended
├─ Affects how long tool runs
└─ Should match actual quiz duration
""")

print("\n" + "=" * 60)
print("All Examples Completed")
print("=" * 60)
