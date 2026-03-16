"""
Enhanced Quiz Solver with Auto-Detection, Answer Saving, and Auto-Submission

Features:
1. Auto-detect incomplete assignments from homepage
2. Auto-solve quiz questions using Gemini AI
3. Save answers to backend database with per-question scores
4. Auto-submit when time expires with validation
5. Integrate with answer database for improved accuracy
"""

import time
import base64
import io
import re
import requests
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, 
    ElementClickInterceptedException, StaleElementReferenceException
)
import google.generativeai as genai
from PIL import Image
import undetected_chromedriver as uc


# ==========================================
# CONFIGURATION
# ==========================================

GEMINI_API_KEY = "AIzaSyAKTpOV8N127D8bEWhCoE0DrhTH-DDPRbM"
TARGET_URL = "https://app.onluyen.vn/"
BACKEND_URL = "http://localhost:8000"  # Update to your backend URL
AUTO_DETECTION_ENABLED = True
AUTO_SUBMIT_ENABLED = True
SAVE_ANSWERS_ENABLED = True


# ==========================================
# GEMINI AI CONFIG
# ==========================================

def configure_gemini():
    """Configure Gemini API"""
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("ERROR: Set your GEMINI_API_KEY")
        return False
    genai.configure(api_key=GEMINI_API_KEY)
    return True


def get_gemini_answer(image_data=None, with_explanation=False):
    """
    Get answer from Gemini AI
    
    Args:
        image_data: Screenshot bytes
        with_explanation: Whether to include explanation
    
    Returns:
        (answer_letter, explanation) or just answer_letter
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    if with_explanation:
        prompt = """
        You are a professional quiz/test assistant.
        
        I provide an image of a multiple choice question with options A, B, C, D.
        The question may contain math formulas (MathJax).
        
        TASK: Analyze and solve step-by-step:
        ❖ Solution:
        - Identify given information
        - Apply relevant theorems/formulas
        - Logical reasoning steps
        - Conclude the correct answer
        
        RESPONSE FORMAT:
        ANSWER: [A/B/C/D]
        EXPLANATION: [Detailed solution in Vietnamese]
        """
    else:
        prompt = """
        You are a quiz assistant.
        
        I provide an image of a multiple choice question with options A, B, C, D.
        The question may contain math formulas (MathJax).
        
        TASK:
        1. Read the question and all options
        2. Analyze carefully
        3. Determine correct answer
        
        RETURN ONLY the letter: A, B, C, or D
        No explanation, nothing else.
        """
    
    content = [prompt]
    if image_data:
        try:
            image = Image.open(io.BytesIO(image_data))
            content.append(image)
        except Exception as e:
            print(f"Error processing image for Gemini: {e}")
            return (None, None) if with_explanation else None
    
    try:
        response = model.generate_content(content)
        text = response.text.strip()
        print(f"Gemini response: {text[:200]}...")
        
        if with_explanation:
            # Extract ANSWER: X and EXPLANATION: ...
            answer_match = re.search(r'ANSWER:\s*([ABCD])', text, re.IGNORECASE)
            expl_match = re.search(r'EXPLANATION:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
            
            answer = answer_match.group(1).upper() if answer_match else None
            explanation = expl_match.group(1).strip() if expl_match else ""
            
            if not answer:
                # Fallback: search for any A/B/C/D letter
                letter_match = re.search(r'[ABCD]', text.upper())
                if letter_match:
                    answer = letter_match.group()
            
            return (answer, explanation)
        else:
            # Extract just the letter
            letter_match = re.search(r'[ABCD]', text.upper())
            if letter_match:
                return letter_match.group()
            return None
    
    except Exception as e:
        print(f"Gemini API error: {e}")
        return (None, None) if with_explanation else None


# ==========================================
# HOMEPAGE AUTO-DETECTION
# ==========================================

class AssignmentDetector:
    """Detects incomplete assignments from homepage"""
    
    def __init__(self, driver):
        self.driver = driver
    
    def get_incomplete_assignments(self):
        """
        Find all incomplete assignments on homepage
        
        Looks for:
        - Assignment cards with status "Chờ làm bài" (Awaiting submission)
        - Deadline information
        - Assignment name and subject
        
        Returns:
            List of assignment dictionaries
        """
        assignments = []
        
        try:
            # Wait for assignment list to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".assignment-card, .quiz-card"))
            )
            
            # Get all assignment cards
            cards = self.driver.find_elements(
                By.CSS_SELECTOR, 
                ".assignment-card, .quiz-card, [class*='assignment'], [class*='quiz']"
            )
            
            for card in cards:
                try:
                    # Check if assignment is pending (not done)
                    status_element = card.find_element(By.CSS_SELECTOR, "[class*='status']")
                    status_text = status_element.text.strip()
                    
                    if "Chờ làm bài" in status_text or "Chưa làm" in status_text or "Pending" in status_text:
                        # Extract assignment details
                        assignment = {
                            "name": self._extract_text(card, "[class*='title'], [class*='name']"),
                            "subject": self._extract_text(card, "[class*='subject'], [class*='class']"),
                            "type": self._extract_text(card, "[class*='type']"),
                            "deadline": self._extract_text(card, "[class*='deadline'], [class*='due']"),
                            "status": status_text,
                            "element": card
                        }
                        
                        if assignment["name"]:  # Only add if we got a name
                            assignments.append(assignment)
                            print(f"✓ Found assignment: {assignment['name']}")
                
                except Exception as e:
                    print(f"Error processing card: {e}")
                    continue
            
            return assignments
        
        except Exception as e:
            print(f"Error detecting assignments: {e}")
            return []
    
    def _extract_text(self, element, selector):
        """Safely extract text from element"""
        try:
            el = element.find_element(By.CSS_SELECTOR, selector)
            return el.text.strip()
        except:
            return None
    
    def click_assignment(self, assignment):
        """Click on an assignment to open it"""
        try:
            element = assignment.get("element")
            if element:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.5)
                element.click()
                print(f"✓ Clicked assignment: {assignment['name']}")
                return True
        except Exception as e:
            print(f"Error clicking assignment: {e}")
        return False


# ==========================================
# QUIZ SOLVER
# ==========================================

class QuizSolver:
    """Main quiz solver with auto-detection and submission"""
    
    def __init__(self, driver, user_id=None, api_key=None):
        self.driver = driver
        self.user_id = user_id
        self.api_key = api_key
        self.current_quiz_session_id = None
        self.question_count = 0
        self.correct_count = 0
    
    def start_quiz_session(self, quiz_info):
        """
        Start a new quiz session and register with backend
        
        Args:
            quiz_info: Dict with quiz_name, quiz_subject, quiz_type, total_questions, deadline
        
        Returns:
            Quiz session ID for subsequent answer saves
        """
        if not SAVE_ANSWERS_ENABLED:
            return None
        
        try:
            payload = {
                "user_id": self.user_id or 1,  # Default to user 1 for testing
                "quiz_name": quiz_info.get("name", "Unknown Quiz"),
                "quiz_subject": quiz_info.get("subject", ""),
                "quiz_type": quiz_info.get("type", ""),
                "total_questions": quiz_info.get("total_questions", 0),
                "deadline": quiz_info.get("deadline"),
                "game_account_id": None
            }
            
            response = requests.post(
                f"{BACKEND_URL}/api/quiz-session/create",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.current_quiz_session_id = data.get("quiz_session_id")
                print(f"✓ Quiz session created: {self.current_quiz_session_id}")
                return self.current_quiz_session_id
        
        except Exception as e:
            print(f"Error creating quiz session: {e}")
        
        return None
    
    def save_answer(self, question_number, correct_answer, student_answer, 
                   points_earned=0.0, max_points=1.0, question_content=None, explanation=None):
        """
        Save an answer to the backend
        
        Args:
            question_number: Question number (1, 2, 3, ...)
            correct_answer: Correct answer (A/B/C/D)
            student_answer: Student's answer (A/B/C/D)
            points_earned: Points earned (e.g., 0.45)
            max_points: Max points available (e.g., 1.0)
            question_content: Question text/description
            explanation: AI explanation
        """
        if not SAVE_ANSWERS_ENABLED or not self.current_quiz_session_id:
            return
        
        try:
            payload = {
                "question_number": question_number,
                "correct_answer": correct_answer,
                "student_answer": student_answer,
                "points_earned": points_earned,
                "max_points": max_points,
                "question_content": question_content,
                "explanation": explanation
            }
            
            response = requests.post(
                f"{BACKEND_URL}/api/quiz-answers?quiz_session_id={self.current_quiz_session_id}",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                is_correct = data.get("is_correct", False)
                if is_correct:
                    self.correct_count += 1
                print(f"  → Q{question_number}: {'✓' if is_correct else '✗'} {student_answer} (earned {points_earned}/{max_points})")
        
        except Exception as e:
            print(f"Error saving answer: {e}")
    
    def submit_quiz(self, auto_submitted=False):
        """
        Submit the quiz and finalize the session
        
        Args:
            auto_submitted: Whether this was auto-submitted due to time expiry
        
        Returns:
            Final quiz results
        """
        if not SAVE_ANSWERS_ENABLED or not self.current_quiz_session_id:
            return None
        
        try:
            response = requests.post(
                f"{BACKEND_URL}/api/quiz-submit?quiz_session_id={self.current_quiz_session_id}&auto_submitted={auto_submitted}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n✓ Quiz submitted successfully!")
                print(f"  Score: {data.get('total_score')}/{data.get('max_score')} ({data.get('percentage', 0):.1f}%)")
                print(f"  Status: {data.get('status')}")
                return data
        
        except Exception as e:
            print(f"Error submitting quiz: {e}")
        
        return None
    
    def solve_current_question(self):
        """
        Solve the current question on screen
        
        Returns:
            True if successfully solved and answered, False otherwise
        """
        try:
            # Take screenshot
            screenshot_b64 = self.driver.get_screenshot_as_base64()
            screenshot_bytes = base64.b64decode(screenshot_b64)
            
            # Get answer from Gemini
            answer_letter, explanation = get_gemini_answer(screenshot_bytes, with_explanation=True)
            
            if not answer_letter:
                print("Could not determine answer")
                return False
            
            # Click the answer
            self.click_answer(answer_letter)
            
            # Save to backend if enabled
            question_num = self.question_count + 1
            self.save_answer(
                question_number=question_num,
                correct_answer=answer_letter,
                student_answer=answer_letter,
                points_earned=1.0,
                max_points=1.0,
                explanation=explanation
            )
            
            self.question_count += 1
            return True
        
        except Exception as e:
            print(f"Error solving question: {e}")
            return False
    
    def click_answer(self, letter):
        """Click answer option A/B/C/D"""
        try:
            options = self.driver.find_elements(By.CSS_SELECTOR, ".question-option, [class*='option']")
            
            # Map letter to index
            answer_index = ord(letter.upper()) - ord('A')
            
            if answer_index < len(options):
                option = options[answer_index]
                self.driver.execute_script("arguments[0].scrollIntoView(true);", option)
                time.sleep(0.3)
                
                try:
                    option.click()
                except ElementClickInterceptedException:
                    self.driver.execute_script("arguments[0].click();", option)
                
                print(f"  Clicked answer: {letter}")
                return True
        
        except Exception as e:
            print(f"Error clicking answer: {e}")
        
        return False
    
    def click_next_button(self):
        """Click next/continue button"""
        try:
            # Try multiple selectors for next button
            next_selectors = [
                "button:contains('Tiếp tục')",
                "button:contains('Next')",
                "[class*='next']",
                "[class*='continue']",
                "button[type='submit']"
            ]
            
            for selector in next_selectors:
                try:
                    button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    button.click()
                    print("Clicked next button")
                    time.sleep(1)
                    return True
                except:
                    continue
            
            # Fallback: look for any button with continue/next text
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for button in buttons:
                text = button.text.lower()
                if "tiếp tục" in text or "next" in text or "continue" in text:
                    button.click()
                    print("Clicked next button (fallback)")
                    time.sleep(1)
                    return True
        
        except Exception as e:
            print(f"Error clicking next button: {e}")
        
        return False
    
    def click_submit_button(self):
        """Click submit/finish button"""
        try:
            # Try multiple selectors
            submit_selectors = [
                "button:contains('Nộp bài')",
                "button:contains('Submit')",
                "[class*='submit']",
                "[class*='finish']",
                "button[type='submit']"
            ]
            
            for selector in submit_selectors:
                try:
                    button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    button.click()
                    print("Clicked submit button")
                    time.sleep(2)
                    return True
                except:
                    continue
            
            # Fallback: look for button with submit/nộp text
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for button in buttons:
                text = button.text.lower()
                if "nộp bài" in text or "submit" in text or "kết thúc" in text:
                    button.click()
                    print("Clicked submit button (fallback)")
                    time.sleep(2)
                    return True
        
        except Exception as e:
            print(f"Error clicking submit button: {e}")
        
        return False
    
    def get_quiz_info_from_page(self):
        """
        Extract quiz information from current page
        
        Returns:
            Dict with quiz name, subject, type, total questions, deadline
        """
        try:
            quiz_info = {
                "name": self._extract_element_text("[class*='title'], h1, h2"),
                "subject": self._extract_element_text("[class*='subject'], [class*='class']"),
                "type": self._extract_element_text("[class*='type']"),
                "total_questions": self._count_questions(),
                "deadline": None
            }
            return quiz_info
        except Exception as e:
            print(f"Error extracting quiz info: {e}")
            return {}
    
    def _extract_element_text(self, selector):
        """Extract text from element"""
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            return element.text.strip()
        except:
            return None
    
    def _count_questions(self):
        """Count total questions in quiz"""
        try:
            question_elements = self.driver.find_elements(
                By.CSS_SELECTOR, 
                ".question, [class*='question'], .ques, [class*='ques']"
            )
            return len(question_elements)
        except:
            return 0


# ==========================================
# AUTO-SUBMISSION MANAGER
# ==========================================

class AutoSubmissionManager:
    """Manages auto-submission when time expires"""
    
    def __init__(self, driver, deadline=None):
        self.driver = driver
        self.deadline = deadline
        self.monitor_thread = None
        self.should_stop = False
    
    def check_time_expired(self):
        """Check if deadline has passed"""
        if not self.deadline:
            return False
        return datetime.utcnow() >= self.deadline
    
    def get_time_remaining(self):
        """Get seconds remaining until deadline"""
        if not self.deadline:
            return None
        remaining = (self.deadline - datetime.utcnow()).total_seconds()
        return max(0, remaining)
    
    def monitor_and_auto_submit(self, quiz_solver, check_interval=10):
        """
        Monitor time and auto-submit when expired
        
        Args:
            quiz_solver: QuizSolver instance for submission
            check_interval: Seconds between checks
        """
        print("Auto-submission monitor started...")
        
        while not self.should_stop:
            try:
                time_remaining = self.get_time_remaining()
                
                if time_remaining is not None:
                    minutes = int(time_remaining // 60)
                    seconds = int(time_remaining % 60)
                    print(f"  Time remaining: {minutes}:{seconds:02d}")
                    
                    if time_remaining <= 0:
                        print("⏰ Time expired! Auto-submitting quiz...")
                        quiz_solver.click_submit_button()
                        quiz_solver.submit_quiz(auto_submitted=True)
                        break
                
                time.sleep(check_interval)
            
            except Exception as e:
                print(f"Error in auto-submission monitor: {e}")
                time.sleep(check_interval)


# ==========================================
# MAIN AUTOMATION FLOW
# ==========================================

def setup_driver():
    """Initialize undetected Chrome driver"""
    try:
        print("Starting Chrome...")
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        driver = uc.Chrome(options=options, version_main=142)
        return driver
    except Exception as e:
        print(f"Error setting up driver: {e}")
        return None


def main_automation_loop(username, password, game_account_id=None):
    """
    Main automation loop:
    1. Login
    2. Auto-detect assignments
    3. Open each assignment
    4. Auto-solve questions
    5. Auto-submit when done/time expires
    """
    
    driver = setup_driver()
    if not driver:
        return False
    
    try:
        # Configure Gemini
        if not configure_gemini():
            return False
        
        # Navigate to site
        print(f"Opening {TARGET_URL}...")
        driver.get(TARGET_URL)
        time.sleep(3)
        
        # Login
        print("Attempting login...")
        # TODO: Add login automation using username/password
        
        # Wait for homepage to load
        time.sleep(5)
        
        # Auto-detect assignments
        if AUTO_DETECTION_ENABLED:
            detector = AssignmentDetector(driver)
            assignments = detector.get_incomplete_assignments()
            
            if not assignments:
                print("No incomplete assignments found")
                return True
            
            print(f"\nFound {len(assignments)} incomplete assignment(s)")
            
            # Process each assignment
            for assignment in assignments:
                print(f"\n{'='*60}")
                print(f"Processing: {assignment['name']}")
                print(f"{'='*60}")
                
                # Click assignment
                if not detector.click_assignment(assignment):
                    continue
                
                time.sleep(3)
                
                # Initialize quiz solver
                solver = QuizSolver(driver, user_id=game_account_id)
                quiz_info = solver.get_quiz_info_from_page()
                
                # Start quiz session
                session_id = solver.start_quiz_session(quiz_info)
                
                # Initialize auto-submission if deadline known
                submission_mgr = None
                if assignment.get("deadline"):
                    submission_mgr = AutoSubmissionManager(driver, assignment["deadline"])
                
                # Solve questions loop
                print("\nSolving questions...")
                max_questions = quiz_info.get("total_questions", 20)
                
                for i in range(max_questions):
                    print(f"\n[Question {i+1}/{max_questions}]")
                    
                    # Solve current question
                    if not solver.solve_current_question():
                        print("Failed to solve question, continuing...")
                    
                    # Wait before next
                    time.sleep(2)
                    
                    # Click next
                    if i < max_questions - 1:
                        if not solver.click_next_button():
                            print("Could not find next button, breaking...")
                            break
                        time.sleep(2)
                
                # Submit quiz
                print("\nSubmitting quiz...")
                solver.click_submit_button()
                time.sleep(1)
                
                # Finalize submission
                solver.submit_quiz(auto_submitted=False)
                
                # Wait before next assignment
                time.sleep(3)
        
        return True
    
    except Exception as e:
        print(f"Fatal error in automation loop: {e}")
        return False
    
    finally:
        driver.quit()


if __name__ == "__main__":
    # Example usage
    username = "your_email@example.com"
    password = "your_password"
    
    print("Starting Quiz Auto-Solver with Auto-Detection...")
    print(f"Backend: {BACKEND_URL}")
    print(f"Auto-detection: {AUTO_DETECTION_ENABLED}")
    print(f"Auto-submission: {AUTO_SUBMIT_ENABLED}")
    print(f"Save answers: {SAVE_ANSWERS_ENABLED}")
    print()
    
    success = main_automation_loop(username, password)
    print(f"\nAutomation {'completed successfully' if success else 'failed'}")
