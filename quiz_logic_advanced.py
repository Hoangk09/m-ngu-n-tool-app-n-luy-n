"""
Quiz Solving Logic - Advanced Version with Answer File Support
Supports:
1. Check backend for answer files
2. Use answer file if available
3. Fall back to Gemini if no answer file
4. Check answers after completion
5. Submit or end based on time
6. Optional: Save answers back to backend
7. Auto-detect incomplete assignments from homepage
"""

import time
import random
import base64
import io
import json
import requests
import hashlib
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import google.generativeai as genai
from PIL import Image


class AssignmentDetector:
    """Detects incomplete assignments from homepage"""
    
    def __init__(self, driver):
        self.driver = driver
    
    def get_incomplete_assignments(self):
        """Find incomplete assignments"""
        try:
            # Wait for content to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".class-as"))
            )
            
            # Find all assignment boxes
            boxes = self.driver.find_elements(By.CSS_SELECTOR, ".class-as")
            assignments = []
            
            for box in boxes:
                try:
                    # Get status
                    status_elem = box.find_element(By.CSS_SELECTOR, ".status")
                    status_text = status_elem.text.lower()
                    
                    # Check for incomplete variants
                    if any(s in status_text for s in ["chờ làm", "chưa làm", "dl", "incomplete"]):
                        # Get name
                        name_elem = box.find_element(By.CSS_SELECTOR, ".name-as")
                        name = name_elem.text.strip()
                        
                        # Use current URL as placeholder since these boxes are clicked
                        assignments.append({
                            "name": name,
                            "url": self.driver.current_url,
                            "element": box,
                            "status": "incomplete"
                        })
                except:
                    continue
            return assignments
        except Exception as e:
            # print(f"Error detecting assignments: {e}")
            return []
    
    def click_first_incomplete(self):
        """Click first incomplete assignment and return success status"""
        try:
            assignments = self.get_incomplete_assignments()
            if assignments:
                first = assignments[0]
                if "element" in first:
                    first["element"].click()
                else:
                    self.driver.get(first["url"])
                time.sleep(3)
                return True
            return False
        except Exception as e:
            print(f"Error clicking assignment: {e}")
            return False


class AnswerFileManager:
    """Manages answer files from backend"""
    
    def __init__(self, backend_url):
        self.backend_url = backend_url
    
    def get_quiz_name_from_page(self, driver):
        """Extract quiz name from current page"""
        try:
            # Look for quiz title in various places
            selectors = [
                ".exam-title",
                ".quiz-title h1",
                ".content-header h2",
                "h1",
            ]
            
            for selector in selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    text = elem.text.strip()
                    if text and len(text) > 3:
                        return text
                except:
                    continue
            
            return None
        except Exception as e:
            print(f"Error extracting quiz name: {e}")
            return None
    
    def get_answer_file(self, quiz_name):
        """Request answer file from backend"""
        try:
            # Create hash of quiz name for lookup
            quiz_hash = hashlib.md5(quiz_name.encode()).hexdigest()
            
            response = requests.post(
                f"{self.backend_url}/api/get-answer-file",
                json={"quiz_name": quiz_name, "quiz_hash": quiz_hash},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("answers"):
                    return data.get("answers")  # Format: {1: "A", 2: "B", ...}
            
            return None
        except Exception as e:
            print(f"Error getting answer file: {e}")
            return None
    
    def save_answers_to_backend(self, quiz_name, answers_dict, quiz_details=None):
        """Save solved answers back to backend"""
        try:
            payload = {
                "quiz_name": quiz_name,
                "quiz_hash": hashlib.md5(quiz_name.encode()).hexdigest(),
                "answers": answers_dict,  # {1: "A", 2: "B", ...}
                "timestamp": datetime.now().isoformat(),
                "quiz_details": quiz_details or {}
            }
            
            response = requests.post(
                f"{self.backend_url}/api/save-answer-file",
                json=payload,
                timeout=10
            )
            
            return response.status_code == 200
        except Exception as e:
            print(f"Error saving answer file: {e}")
            return False


class QuestionSolver:
    """Handles solving individual questions"""
    
    def __init__(self, driver, gemini_api_key, answer_file_manager, log_callback=None):
        self.driver = driver
        self.answer_file_manager = answer_file_manager
        self.log_callback = log_callback or print
        
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def _log(self, message):
        """Internal logging"""
        self.log_callback(message)
    
    def get_answer_from_gemini(self, image_data, with_explanation=False):
        """Get answer from Gemini AI with retry logic for rate limits"""
        max_retries = 5
        retry_count = 0
        base_wait = 30  # Base wait time in seconds
        
        while retry_count < max_retries:
            try:
                prompt = """
                Bạn là trợ lý giải bài tập trắc nghiệm chuyên nghiệp.
                
                Tôi cung cấp hình ảnh câu hỏi với các đáp án A, B, C, D.
                Câu hỏi có thể chứa công thức toán học (MathJax).
                
                NHIỆM VỤ: Xác định đáp án đúng.
                
                Trả lời FORMAT:
                - Nếu trắc nghiệm: ANSWER: [A/B/C/D]
                - Nếu đúng/sai: ANSWER: [true/false] cho mỗi câu
                - Nếu trả lời ngắn: ANSWER: [câu trả lời]
                
                Không giải thích, chỉ trả về đáp án!
                """
                
                content = [prompt]
                if image_data:
                    try:
                        image = Image.open(io.BytesIO(image_data))
                        content.append(image)
                    except Exception as e:
                        self._log(f"⚠️ Lỗi xử lý ảnh: {e}")
                        return None
                
                response = self.model.generate_content(content)
                text = response.text.strip().upper()
                
                # Extract answer
                import re
                match = re.search(r'ANSWER:\s*([A-D]|TRUE|FALSE|[^,\n]+)', text)
                if match:
                    return match.group(1)
                
                return None
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a rate limit error
                if '429' in error_str or 'quota' in error_str.lower() or 'rate' in error_str.lower():
                    retry_count += 1
                    wait_time = base_wait * retry_count  # Exponential backoff
                    
                    if retry_count < max_retries:
                        self._log(f"⚠️ Rate limit! Đợi {wait_time}s rồi thử lại ({retry_count}/{max_retries})...")
                        time.sleep(wait_time)
                        continue
                    else:
                        self._log(f"❌ Đã thử {max_retries} lần nhưng vẫn bị rate limit")
                        return None
                else:
                    self._log(f"❌ Lỗi Gemini: {e}")
                    return None
        
        return None
    
    def solve_multiple_choice(self, answer=None):
        """Solve multiple choice question"""
        option_selectors = [
            ".question-option",
            ".answer-option", 
            ".option-item",
            "[class*='option']",
            ".quiz-answer",
            "label.answer"
        ]
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Try multiple selectors to find options
                options = []
                working_selector = None
                
                for selector in option_selectors:
                    try:
                        options = WebDriverWait(self.driver, 2).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                        )
                        if len(options) >= 2:
                            working_selector = selector
                            break
                    except:
                        continue
                
                if len(options) < 2:
                    self._log("⚠️ Không tìm thấy đủ đáp án")
                    return None
                
                if not answer:
                    # Get screenshot and ask Gemini
                    screenshot_png = self.driver.get_screenshot_as_png()
                    answer = self.get_answer_from_gemini(screenshot_png)
                
                if answer and answer in "ABCD":
                    answer_idx = ord(answer) - ord('A')
                    if answer_idx < len(options):
                        # Re-find the specific option to avoid stale element
                        options = self.driver.find_elements(By.CSS_SELECTOR, working_selector)
                        if answer_idx >= len(options):
                            self._log(f"⚠️ Index {answer_idx} vượt quá {len(options)} options")
                            return None
                            
                        target_option = options[answer_idx]
                        
                        # Scroll and click
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_option)
                        time.sleep(0.3)
                        
                        try:
                            target_option.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", target_option)
                        return answer
                
                return None
                
            except Exception as e:
                if "stale" in str(e).lower() and attempt < max_retries - 1:
                    self._log(f"⚠️ Stale element, thử lại ({attempt + 1}/{max_retries})...")
                    time.sleep(0.5)
                    continue
                else:
                    self._log(f"❌ Lỗi giải trắc nghiệm: {e}")
                    return None
        return None
    
    def solve_short_answer(self, answer=None):
        """Solve short answer question"""
        try:
            input_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='text']")
            
            if not answer:
                # Get screenshot and ask Gemini
                screenshot_png = self.driver.get_screenshot_as_png()
                answer = self.get_answer_from_gemini(screenshot_png)
            
            if answer:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", input_field)
                input_field.clear()
                input_field.send_keys(str(answer))
                return answer
            
            return None
        except Exception as e:
            self._log(f"❌ Lỗi giải câu ngắn: {e}")
            return None
    
    def solve_true_false(self, answers=None):
        """Solve true/false questions - using EXACT logic from quiz_solver_multi.py"""
        try:
            # Use exact selector from quiz_solver_multi.py
            containers = self.driver.find_elements(By.CSS_SELECTOR, ".true-false")
            
            if not containers:
                self._log("⚠️ Không tìm thấy câu đúng/sai")
                return None
            
            if not answers:
                # Get Gemini answers for each
                screenshot_png = self.driver.get_screenshot_as_png()
                answers = [self.get_answer_from_gemini(screenshot_png) for _ in containers]
            
            solved_answers = []
            for idx, tf_container in enumerate(containers):
                answer = answers[idx] if idx < len(answers) else "true"
                letter = chr(ord('a') + idx)
                
                try:
                    if answer and answer.upper() in ["TRUE", "ĐÚNG", "Đ", "T"]:
                        radio = tf_container.find_element(By.CSS_SELECTOR, "input[value='true']")
                        label_text = "Đ"
                    else:
                        radio = tf_container.find_element(By.CSS_SELECTOR, "input[value='false']")
                        label_text = "S"
                    
                    radio_id = radio.get_attribute("id")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", radio)
                    
                    # Try clicking via label first (more reliable)
                    try:
                        label = tf_container.find_element(By.CSS_SELECTOR, f"label[for='{radio_id}']")
                        label.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", radio)
                    
                    self._log(f"  Câu {letter}: {label_text}")
                    solved_answers.append(answer)
                except Exception as e:
                    self._log(f"  ⚠️ Lỗi câu {letter}: {e}")
            
            return solved_answers if solved_answers else None
        except Exception as e:
            self._log(f"❌ Lỗi giải đúng/sai: {e}")
            return None


class QuizSolver:
    """Main quiz solver orchestrator"""
    
    def __init__(self, driver, config, log_callback=None):
        self.driver = driver
        self.config = config
        self.log_callback = log_callback or print
        
        self.backend_url = config.get("backend_url", "http://localhost:8000")
        self.answer_manager = AnswerFileManager(self.backend_url)
        self.question_solver = QuestionSolver(
            driver, 
            config.get("api_key"),
            self.answer_manager,
            log_callback
        )
        
        self.answers_dict = {}  # Store all answers: {q_num: answer}
        self.start_time = None
        self.end_time = None
        self.stop_flag = False
    
    def _log(self, message):
        """Internal logging"""
        self.log_callback(message)
    
    def start_quiz(self, quiz_time_minutes):
        """Start quiz solving"""
        self.start_time = time.time()
        self.end_time = self.start_time + (quiz_time_minutes * 60)
        self.stop_flag = False
        self.answers_dict = {}
        
        self._log(f"🚀 Bắt đầu giải bài ({quiz_time_minutes} phút)")
    
    def get_time_remaining(self):
        """Get remaining time in seconds"""
        if not self.end_time:
            return None
        remaining = self.end_time - time.time()
        return max(0, remaining)
    
    def solve_one_question(self, question_number, use_answer_file=None):
        """Solve one question"""
        try:
            remaining = self.get_time_remaining()
            if remaining <= 0:
                self._log("⏰ Hết thời gian!")
                return None
            
            self._log(f"📝 Câu {question_number}... ({int(remaining)}s còn lại)")
            
            # Wait for question to load
            time.sleep(1)
            
            # Detect question type using EXACT selectors from quiz_solver_multi.py
            # Short answer - check FIRST because it's more specific
            short_answer_inputs = self.driver.find_elements(By.CSS_SELECTOR, ".answer-input input[type='text']")
            if not short_answer_inputs:
                short_answer_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[id^='mathplay-answer']")
            
            # True/false
            true_false_containers = self.driver.find_elements(By.CSS_SELECTOR, ".true-false")
            
            # Multiple choice
            options = self.driver.find_elements(By.CSS_SELECTOR, ".question-option")
            
            answer = None
            
            if short_answer_inputs:
                # SHORT ANSWER
                self._log("  📝 Trả lời ngắn")
                answer = self.question_solver.solve_short_answer(
                    answer=use_answer_file.get(question_number) if use_answer_file else None
                )
            elif true_false_containers:
                # TRUE/FALSE
                self._log(f"  ✅❌ Đúng/Sai ({len(true_false_containers)} câu)")
                answers = self.question_solver.solve_true_false(
                    answers=[use_answer_file.get(question_number)] if use_answer_file else None
                )
                answer = answers[0] if answers else None
            elif len(options) >= 2:
                # Multiple choice
                self._log(f"  🔘 Trắc nghiệm ({len(options)} đáp án)")
                answer = self.question_solver.solve_multiple_choice(
                    answer=use_answer_file.get(question_number) if use_answer_file else None
                )
            else:
                self._log("  ⚠️ Không phát hiện loại câu hỏi!")
            
            if answer:
                self.answers_dict[question_number] = answer
                self._log(f"  ✓ Câu {question_number}: {answer}")
                return answer
            else:
                self._log(f"  ✗ Không thể giải câu {question_number}")
                return None
        
        except Exception as e:
            self._log(f"  ❌ Lỗi: {e}")
            return None
    
    def click_answer_button(self):
        """Click 'Trả lời' button"""
        try:
            selectors = [
                # EXACT match for the actual button
                "button.btn-primary",
                ".btn.btn-primary",
                "button.btn.btn-lg.btn-block.btn-primary",
                # XPath with various text patterns
                "//button[contains(text(), 'Trả lời')]",
                "//span[contains(text(), 'Trả lời')]/parent::*",
                "//div[contains(text(), 'Trả lời')]",
                "//*[contains(@class, 'btn')][contains(text(), 'Trả lời')]",
                "//*[contains(@class, 'btn')]/span[contains(text(), 'Trả lời')]/..",
                # CSS patterns
                ".btn-answer",
                ".btn-submit",
                "button[type='submit']",
                ".btn.green",
                ".btn-test.green",
                "[class*='btn'][class*='answer']",
                "[class*='btn'][class*='submit']",
            ]
            
            for selector in selectors:
                try:
                    if selector.startswith("//") or selector.startswith("//*"):
                        btn = WebDriverWait(self.driver, 1).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        btn = WebDriverWait(self.driver, 1).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    time.sleep(0.3)
                    btn.click()
                    self._log("✓ Đã click 'Trả lời'")
                    return True
                except:
                    continue
            
            self._log("⚠️ Không tìm thấy nút 'Trả lời'")
            return False
        except Exception as e:
            self._log(f"❌ Lỗi click button: {e}")
            return False
    
    def is_quiz_finished(self):
        """Check if quiz shows finish button (Kết thúc)"""
        try:
            # Look for finish button
            finish_button = self.driver.find_element(
                By.XPATH,
                "//div[contains(@class, 'btn')]//span[contains(text(), 'Kết thúc')]/parent::div"
            )
            return finish_button is not None
        except:
            return False
    
    def click_finish_button(self):
        """Click 'Kết thúc' button with retry for stale elements"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                selector = "//div[contains(@class, 'btn')]//span[contains(text(), 'Kết thúc')]/parent::div"
                finish_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", finish_btn)
                time.sleep(0.3)
                
                try:
                    finish_btn.click()
                except:
                    # Re-find and use JS click
                    finish_btn = self.driver.find_element(By.XPATH, selector)
                    self.driver.execute_script("arguments[0].click();", finish_btn)
                    
                self._log("✓ Đã click 'Kết thúc'")
                return True
            except Exception as e:
                if "stale" in str(e).lower() and attempt < max_retries - 1:
                    self._log(f"⚠️ Stale element, thử lại ({attempt + 1}/{max_retries})...")
                    time.sleep(0.5)
                    continue
                else:
                    self._log(f"⚠️ Lỗi click Kết thúc: {e}")
                    return False
        return False
    
    def check_and_review_answers(self, should_continue_on_timeout=True):
        """Review answers after completing all questions"""
        self._log("🔍 Bắt đầu kiểm tra đáp án...")
        
        question_num = 1
        while not self.stop_flag:
            remaining = self.get_time_remaining()
            
            if remaining <= 0:
                if should_continue_on_timeout:
                    self._log("⏰ Hết thời gian - Ấn nút kết thúc")
                    self.click_finish_button()
                    break
                else:
                    self._log("⏰ Hết thời gian - Tiếp tục kiểm tra")
                    # Continue checking
            
            try:
                # Look for marked wrong/right answers
                wrong_answers = self.driver.find_elements(
                    By.XPATH,
                    "//div[contains(@class, 'question') and contains(@class, 'wrong')]"
                )
                
                right_answers = self.driver.find_elements(
                    By.XPATH,
                    "//div[contains(@class, 'question') and contains(@class, 'right')]"
                )
                
                self._log(f"📊 Kiểm tra: {len(right_answers)} đúng, {len(wrong_answers)} sai")
                
                # Try to navigate to next question or finish
                if not self.click_next_or_finish():
                    break
                
                question_num += 1
                time.sleep(1)
                
            except Exception as e:
                self._log(f"⚠️ Lỗi kiểm tra: {e}")
                break
    
    def click_next_or_finish(self):
        """Click next question or finish button"""
        try:
            # Try next button first
            try:
                next_btn = self.driver.find_element(
                    By.XPATH,
                    "//span[contains(text(), 'Tiếp tục')]/parent::div"
                )
                next_btn.click()
                self._log("▶ Tiếp tục câu tiếp theo")
                time.sleep(1)
                return True
            except:
                pass
            
            # Try finish button
            try:
                finish_btn = self.driver.find_element(
                    By.XPATH,
                    "//span[contains(text(), 'Kết thúc')]/parent::div"
                )
                finish_btn.click()
                self._log("✓ Hoàn thành")
                return False
            except:
                pass
            
            return False
        except Exception as e:
            self._log(f"⚠️ Lỗi click next/finish: {e}")
            return False
    
    def submit_answers_to_backend(self, quiz_name):
        """Save answers to backend"""
        if not self.answers_dict:
            self._log("⚠️ Không có đáp án để lưu")
            return False
        
        try:
            self._log("💾 Lưu đáp án vào backend...")
            success = self.answer_manager.save_answers_to_backend(
                quiz_name,
                self.answers_dict,
                {
                    "total_questions": len(self.answers_dict),
                    "solved_time": datetime.now().isoformat(),
                    "elapsed_seconds": time.time() - self.start_time
                }
            )
            
            if success:
                self._log(f"✅ Đã lưu {len(self.answers_dict)} câu")
            else:
                self._log("⚠️ Không thể lưu đáp án")
            
            return success
        except Exception as e:
            self._log(f"❌ Lỗi lưu đáp án: {e}")
            return False
    
    def go_to_assignment_page(self):
        """Navigate to assignment page to get answer file"""
        try:
            self._log("📂 Đang vào trang bài tập...")
            self.driver.get("https://app.onluyen.vn/school/student/assignment?view=1&status=0")
            time.sleep(3)
            return True
        except Exception as e:
            self._log(f"❌ Lỗi vào trang bài tập: {e}")
            return False
    
    def find_and_open_last_quiz(self, quiz_name):
        """Find and open the last completed quiz"""
        try:
            self._log(f"🔍 Tìm bài '{quiz_name}' trong danh sách...")
            
            # Wait for assignments to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".class-as"))
            )
            
            assignments = self.driver.find_elements(By.CSS_SELECTOR, ".class-as")
            
            for assignment in assignments:
                try:
                    name_elem = assignment.find_element(By.CSS_SELECTOR, ".name-as .name")
                    name_text = name_elem.text.strip()
                    
                    if quiz_name.lower() in name_text.lower():
                        self._log(f"✓ Tìm thấy: {name_text}")
                        
                        # Click on assignment
                        assignment.click()
                        time.sleep(2)
                        return True
                except:
                    continue
            
            self._log(f"⚠️ Không tìm thấy bài '{quiz_name}'")
            return False
        except Exception as e:
            self._log(f"❌ Lỗi tìm bài: {e}")
            return False
    
    def click_chi_tiet_button(self):
        """Click 'Chi tiết' button to see answer page"""
        try:
            self._log("📋 Ấn nút 'Chi tiết'...")
            
            chi_tiet_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Chi tiết')]"))
            )
            
            self.driver.execute_script("arguments[0].scrollIntoView(true);", chi_tiet_btn)
            chi_tiet_btn.click()
            time.sleep(2)
            return True
        except Exception as e:
            self._log(f"❌ Lỗi click Chi tiết: {e}")
            return False
    
    def scrape_answer_page(self):
        """Scrape answers from the answer review page"""
        try:
            self._log("📸 Tải đáp án từ trang chi tiết...")
            
            answers_dict = {}
            
            # Find all questions on page
            questions = self.driver.find_elements(By.CSS_SELECTOR, ".question-item")
            
            for idx, question in enumerate(questions, 1):
                try:
                    # Find correct answer mark
                    correct_elem = question.find_element(By.CSS_SELECTOR, ".answer-item.correct")
                    answer_text = correct_elem.text.strip()
                    
                    # Extract letter (A, B, C, D) or content
                    if answer_text[0] in "ABCD":
                        answer = answer_text[0]
                    else:
                        answer = answer_text
                    
                    answers_dict[idx] = answer
                    self._log(f"  Câu {idx}: {answer}")
                except:
                    continue
            
            return answers_dict if answers_dict else None
        except Exception as e:
            self._log(f"❌ Lỗi tải đáp án: {e}")
            return None


# ============================================
# MAIN SOLVING FLOW
# ============================================

def solve_quiz(driver, config, log_callback=None):
    """
    Main quiz solving flow:
    1. Auto-detect incomplete assignments if enabled
    2. Get quiz name
    3. Ask backend for answer file
    4. If found, use it; else use Gemini
    5. Solve all questions
    6. Check time - if time left, review answers
    7. Optionally save answers to backend
    """
    
    log_fn = log_callback or print
    
    try:
        # Auto-detect assignments if enabled
        if config.get("auto_detect", False):
            log_fn("🔍 Tìm bài chưa làm trên trang chủ...")
            detector = AssignmentDetector(driver)
            
            if detector.click_first_incomplete():
                log_fn("✅ Mở bài chưa làm đầu tiên")
                time.sleep(3)
            else:
                log_fn("⚠️ Không tìm thấy bài chưa làm")
                return False
        
        # Initialize solver
        solver = QuizSolver(driver, config, log_fn)
        
        # Get quiz name
        quiz_name = solver.answer_manager.get_quiz_name_from_page(driver)
        if not quiz_name:
            log_fn("❌ Không thể lấy tên bài")
            return False
        
        log_fn(f"📚 Tên bài: {quiz_name}")
        
        # Try to get answer file from backend
        answer_file = solver.answer_manager.get_answer_file(quiz_name)
        if answer_file:
            log_fn("✅ Tìm thấy file đáp án từ backend")
        else:
            log_fn("🔍 Chưa có file đáp án, sẽ dùng Gemini API")
        
        # Start quiz
        quiz_time = config.get("quiz_time", 45)
        solver.start_quiz(quiz_time)
        
        # Solve all questions
        question_num = 1
        consecutive_failures = 0
        max_consecutive_failures = 3  # Only stop if 3 questions fail in a row
        
        while not solver.stop_flag:
            remaining = solver.get_time_remaining()
            if remaining <= 0:
                log_fn("⏰ Hết thời gian!")
                break
            
            # Solve one question
            answer = solver.solve_one_question(
                question_num,
                use_answer_file=answer_file
            )
            
            if not answer:
                consecutive_failures += 1
                log_fn(f"  ✗ Không thể giải câu {question_num} ({consecutive_failures}/{max_consecutive_failures})")
                
                if consecutive_failures >= max_consecutive_failures:
                    log_fn("⚠️ Quá nhiều câu thất bại liên tiếp, chuyển sang câu tiếp theo...")
                    # Try to skip to next question
                    solver.click_next_or_finish()
                    time.sleep(1)
                    consecutive_failures = 0  # Reset counter
            else:
                consecutive_failures = 0  # Reset on success
            
            # Click answer button (even if failed, to move to next question)
            time.sleep(0.5)
            if answer:
                solver.click_answer_button()
            time.sleep(random.uniform(2, 4))
            
            # Check if finished
            if solver.is_quiz_finished():
                log_fn("✓ Hoàn thành tất cả câu hỏi")
                break
            
            question_num += 1
            
            # Safety: don't go beyond 100 questions
            if question_num > 100:
                log_fn("⚠️ Đã đến câu 100, dừng lại")
                break
        
        # Check time and review answers if time left
        remaining = solver.get_time_remaining()
        if remaining > 30:  # More than 30 seconds left
            should_continue = config.get("continue_on_timeout", True)
            solver.check_and_review_answers(should_continue)
        
        # Click finish button
        solver.click_finish_button()
        time.sleep(2)
        
        # Save answers to backend if enabled
        if config.get("save_answers", False):
            if not answer_file:  # Only save if we didn't use existing file
                log_fn("💾 Lưu đáp án mới vào backend...")
                
                # Wait for submission
                time.sleep(10)
                
                # Go to assignment page
                if solver.go_to_assignment_page():
                    # Find and open last quiz
                    if solver.find_and_open_last_quiz(quiz_name):
                        # Click Chi tiết
                        if solver.click_chi_tiet_button():
                            # Scrape answers
                            scraped_answers = solver.scrape_answer_page()
                            if scraped_answers:
                                solver.submit_answers_to_backend(quiz_name)
        
        log_fn("✅ Hoàn thành!")
        return True
    
    except Exception as e:
        log_fn(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        return False
