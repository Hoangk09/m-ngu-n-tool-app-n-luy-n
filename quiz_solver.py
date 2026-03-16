
import time
import os
import base64
import io
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import google.generativeai as genai
from PIL import Image

# ==========================================
# CONFIGURATION
# ==========================================
# REPLACE WITH YOUR ACTUAL API KEY
GEMINI_API_KEY = "AIzaSyAKTpOV8N127D8bEWhCoE0DrhTH-DDPRbM" 

# URL to open
TARGET_URL = "https://app.onluyen.vn/"

# ==========================================
# SETUP
# ==========================================

import undetected_chromedriver as uc

def setup_driver():
    """Initializes the Selenium WebDriver using undetected-chromedriver."""
    try:
        print("Starting undetected Chrome...")
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        # options.add_argument("--user-data-dir=C:\\selenium\\ChromeProfile") # Optional: Persist login
        
        # Force using ChromeDriver version 142 to match installed browser
        driver = uc.Chrome(options=options, version_main=142)
        return driver
    except Exception as e:
        print(f"Error setting up undetected Chrome driver: {e}")
        return None

def configure_gemini():
    """Configures the Gemini API."""
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("ERROR: Please set your GEMINI_API_KEY in the script.")
        return False
    genai.configure(api_key=GEMINI_API_KEY)
    return True

def get_gemini_response(image_data=None, with_explanation=False):
    """
    Sends the question to Gemini and gets the answer letter (A/B/C/D).
    If with_explanation=True, also returns the explanation.
    Returns: (answer_letter, explanation) or just answer_letter
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    if with_explanation:
        prompt = """
        Bạn là trợ lý giải bài tập trắc nghiệm chuyên nghiệp.
        
        Tôi cung cấp hình ảnh câu hỏi với các đáp án A, B, C, D.
        Câu hỏi có thể chứa công thức toán học (MathJax).
        
        NHIỆM VỤ: Phân tích và giải bài theo các bước:
        
        ❖ Giải đáp:
        - Xác định dữ kiện đề bài
        - Áp dụng định lý/công thức liên quan
        - Lập luận từng bước logic
        - Kết luận đáp án đúng
        
        TRẢ LỜI THEO FORMAT:
        ANSWER: [A/B/C/D]
        EXPLANATION: [Lời giải chi tiết bằng tiếng Việt, có thể có nhiều cách giải]
        """
    else:
        prompt = """
        Bạn là trợ lý giải bài tập trắc nghiệm.
        
        Tôi cung cấp hình ảnh câu hỏi trắc nghiệm với các đáp án A, B, C, D.
        Câu hỏi có thể chứa công thức toán học được render bằng MathJax.
        
        NHIỆM VỤ: 
        1. Đọc kỹ nội dung câu hỏi và tất cả các đáp án
        2. Phân tích bài toán
        3. Xác định đáp án đúng
        
        CHÚ Ý QUAN TRỌNG:
        - Với bài hình học không gian: chú ý mối quan hệ song song, vuông góc
        - Với bài đại số: tính toán cẩn thận
        - Với bài xác suất/thống kê: áp dụng đúng công thức
        
        TRẢ LỜI: CHỈ trả về MỘT chữ cái A, B, C hoặc D.
        Không giải thích, không thêm gì khác.
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
        print(f"Gemini raw response: {text[:300]}...")
        
        import re
        
        explanation = ""
        answer = None
        
        # Try to extract ANSWER: X format first
        answer_match = re.search(r'ANSWER:\s*([ABCD])', text, re.IGNORECASE)
        if answer_match:
            answer = answer_match.group(1).upper()
            # Extract explanation
            expl_match = re.search(r'EXPLANATION:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
            if expl_match:
                explanation = expl_match.group(1).strip()
        
        # Fallback methods if ANSWER: format not found
        if not answer:
            # Method 1: Try to find JSON format {"answer": "X"}
            json_match = re.search(r'"answer"\s*:\s*"?([ABCD])"?', text, re.IGNORECASE)
            if json_match:
                answer = json_match.group(1).upper()
            
            # Method 2: Try to find \boxed{X} format (LaTeX) 
            if not answer:
                boxed_match = re.search(r'\\boxed\{[^}]*?([ABCD])[^}]*\}', text, re.IGNORECASE)
                if boxed_match:
                    answer = boxed_match.group(1).upper()
            
            # Method 3: Look for "answer is X" pattern
            if not answer:
                answer_pattern = re.search(r'(?:answer|đáp án|correct)(?:\s+is|\s+là|:)?\s*\(?([ABCD])\)?', text, re.IGNORECASE)
                if answer_pattern:
                    answer = answer_pattern.group(1).upper()
            
            # Method 4: If response is very short, extract letter directly
            if not answer and len(text) < 10:
                letter_match = re.search(r'[ABCD]', text.upper())
                if letter_match:
                    answer = letter_match.group()
            
            # Method 5: Find the last A/B/C/D letter
            if not answer:
                all_letters = re.findall(r'\b([ABCD])\b', text.upper())
                if all_letters:
                    answer = all_letters[-1]
            
            # Use full text as explanation if with_explanation
            if with_explanation and not explanation:
                explanation = text
        
        if answer:
            print(f"Extracted answer: {answer}")
            if with_explanation:
                return (answer, explanation)
            return answer
        
        print(f"Could not find answer in response")
        return (None, None) if with_explanation else None
            
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return (None, None) if with_explanation else None


def get_true_false_response(image_data=None, num_statements=4):
    """
    Sends the question to Gemini and gets True/False answers for each statement.
    Returns a list like ["true", "false", "true", "false"] for a, b, c, d.
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are a helpful assistant that solves True/False questions in Vietnamese.
    
    I have provided an image of a question with {num_statements} statements (labeled a, b, c, d or similar).
    Each statement needs to be evaluated as "Đúng" (True) or "Sai" (False).
    
    Task: For each statement, determine if it is True or False.
    
    IMPORTANT: Reply with ONLY a single JSON object, nothing else.
    Output format: {{"answers": ["true", "false", "true", "false"]}}
    
    Where each element is either "true" or "false" corresponding to statements a, b, c, d in order.
    
    Example for 4 statements: {{"answers": ["true", "false", "true", "false"]}}
    """
    
    content = [prompt]
    if image_data:
        try:
            image = Image.open(io.BytesIO(image_data))
            content.append(image)
        except Exception as e:
            print(f"Error processing image for Gemini: {e}")
            return None

    try:
        response = model.generate_content(content)
        text = response.text.strip()
        print(f"Gemini raw response (True/False): {text}")
        
        # Robust JSON extraction using regex
        import re
        import json
        
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group()
            data = json.loads(json_str)
            answers = data.get("answers", [])
            # Normalize to lowercase
            return [str(a).lower() for a in answers]
        else:
            print(f"Could not find JSON in response: {text}")
            return None
            
    except Exception as e:
        print(f"Error calling Gemini API (True/False): {e}")
        return None


def get_short_answer_response(image_data=None):
    """
    Sends the question to Gemini and gets a short numeric answer.
    Returns a string containing only digits, '-', and ','.
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = """
    You are a helpful assistant that solves math/science questions requiring a short numeric answer.
    
    I have provided an image of a question that requires a SHORT ANSWER (not multiple choice).
    
    Task: Calculate or determine the correct answer.
    
    CRITICAL: Your response must be ONLY the final numeric answer.
    - Just the number, nothing else
    - Use comma as decimal separator if needed (e.g., "3,5" for 3.5)
    - For negative numbers use minus sign (e.g., "-5")
    - Do NOT include units, explanations, or any other text
    
    Examples of correct responses:
    42
    -15
    3,5
    229
    """
    
    content = [prompt]
    if image_data:
        try:
            image = Image.open(io.BytesIO(image_data))
            content.append(image)
        except Exception as e:
            print(f"Error processing image for Gemini: {e}")
            return None

    try:
        response = model.generate_content(content)
        text = response.text.strip()
        print(f"Gemini raw response (Short Answer): {text[:200]}...")  # Only print first 200 chars
        
        import re
        import json
        
        # Method 1: Try to find JSON format
        json_match = re.search(r'\{[^}]*"answer"\s*:\s*"?([^"}\s,]+)"?[^}]*\}', text)
        if json_match:
            answer = json_match.group(1)
            cleaned = re.sub(r'[^0-9,\-]', '', answer)
            if cleaned:
                print(f"Extracted from JSON: {cleaned}")
                return cleaned
        
        # Method 2: Try to find \boxed{...} format (LaTeX)
        boxed_match = re.search(r'\\boxed\{[^}]*?(\-?[\d,]+)[^}]*\}', text)
        if boxed_match:
            answer = boxed_match.group(1)
            cleaned = re.sub(r'[^0-9,\-]', '', answer)
            if cleaned:
                print(f"Extracted from \\boxed: {cleaned}")
                return cleaned
        
        # Method 3: Look for "answer is X" or "đáp án là X" patterns
        answer_pattern = re.search(r'(?:answer|đáp án|kết quả|result)(?:\s+is|\s+là|:)?\s*[\[\(]?\s*(\-?[\d,]+)', text, re.IGNORECASE)
        if answer_pattern:
            answer = answer_pattern.group(1)
            cleaned = re.sub(r'[^0-9,\-]', '', answer)
            if cleaned:
                print(f"Extracted from pattern: {cleaned}")
                return cleaned
        
        # Method 4: If response is very short, it might be just the answer
        if len(text) < 20:
            cleaned = re.sub(r'[^0-9,\-]', '', text)
            if cleaned:
                print(f"Extracted (short response): {cleaned}")
                return cleaned
        
        # Method 5: Find the last number in the response (often the final answer)
        all_numbers = re.findall(r'\-?[\d]+(?:,\d+)?', text)
        if all_numbers:
            answer = all_numbers[-1]  # Take the last number
            print(f"Extracted (last number): {answer}")
            if with_explanation:
                return (answer, text)
            return answer
        
        print(f"Could not find answer in response")
        return (None, None) if with_explanation else None
            
    except Exception as e:
        print(f"Error calling Gemini API (Short Answer): {e}")
        return (None, None) if with_explanation else None

def get_true_false_response(image_data=None, num_statements=4, with_explanation=False):
    """
    Sends the question to Gemini and gets True/False answers for each statement.
    Returns a list like ["true", "false", "true", "false"] for a, b, c, d.
    If with_explanation=True, returns (answers_list, explanation).
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    if with_explanation:
        prompt = f"""
        You are a helpful assistant that solves True/False questions in Vietnamese.
        
        I have provided an image of a question with {num_statements} statements (labeled a, b, c, d or similar).
        Each statement needs to be evaluated as "Đúng" (True) or "Sai" (False).
        
        Task: For each statement, determine if it is True or False AND EXPLAIN WHY.
        
        Reply in this EXACT format:
        ANSWERS: ["true", "false", "true", "false"]
        EXPLANATION: [Your detailed explanation for each statement]
        """
    else:
        prompt = f"""
        You are a helpful assistant that solves True/False questions in Vietnamese.
        
        I have provided an image of a question with {num_statements} statements (labeled a, b, c, d or similar).
        Each statement needs to be evaluated as "Đúng" (True) or "Sai" (False).
        
        Task: For each statement, determine if it is True or False.
        
        IMPORTANT: Reply with ONLY a single JSON object, nothing else.
        Output format: {{"answers": ["true", "false", "true", "false"]}}
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
        print(f"Gemini raw response (True/False): {text[:300]}...")
        
        import re
        import json
        
        answers = []
        explanation = ""
        
        # Try to extract ANSWERS: [...] format first
        answers_match = re.search(r'ANSWERS:\s*(\[.*?\])', text, re.IGNORECASE | re.DOTALL)
        if answers_match:
            try:
                answers = json.loads(answers_match.group(1).replace("'", '"'))
                # Extract explanation
                expl_match = re.search(r'EXPLANATION:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
                if expl_match:
                    explanation = expl_match.group(1).strip()
            except:
                pass
        
        # Fallback to JSON extraction
        if not answers:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                json_str = match.group()
                try:
                    data = json.loads(json_str)
                    answers = data.get("answers", [])
                except:
                    pass
        
        # Use full text as explanation if needed
        if with_explanation and not explanation:
            explanation = text
            
        if answers:
            normalized_answers = [str(a).lower() for a in answers]
            if with_explanation:
                return (normalized_answers, explanation)
            return normalized_answers
        else:
            print(f"Could not find answers in response")
            return (None, None) if with_explanation else None
            
    except Exception as e:
        print(f"Error calling Gemini API (True/False): {e}")
        return (None, None) if with_explanation else None


def get_short_answer_response(image_data=None, with_explanation=False):
    """
    Sends the question to Gemini and gets a short numeric answer.
    Returns a string containing only digits, '-', and ','.
    If with_explanation=True, returns (answer, explanation).
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    if with_explanation:
        prompt = """
        You are a helpful assistant that solves math/science questions requiring a short numeric answer.
        
        I have provided an image of a question that requires a SHORT ANSWER (not multiple choice).
        
        Task: Calculate or determine the correct answer and EXPLAIN the steps.
        
        Reply in this EXACT format:
        ANSWER: [Your numeric answer]
        EXPLANATION: [Your detailed step-by-step solution]
        
        Rules for ANSWER:
        - Only digits, minus sign (-), and comma (,)
        - No units or text
        """
    else:
        prompt = """
        You are a helpful assistant that solves math/science questions requiring a short numeric answer.
        
        I have provided an image of a question that requires a SHORT ANSWER (not multiple choice).
        
        Task: Calculate or determine the correct answer.
        
        CRITICAL: Your response must be ONLY the final numeric answer.
        - Just the number, nothing else
        - Use comma as decimal separator if needed (e.g., "3,5" for 3.5)
        - For negative numbers use minus sign (e.g., "-5")
        - Do NOT include units, explanations, or any other text
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
        print(f"Gemini raw response (Short Answer): {text[:200]}...")
        
        import re
        import json
        
        answer = None
        explanation = ""
        
        # Try to extract ANSWER: X format first (support both . and , as decimal)
        answer_match = re.search(r'ANSWER:\s*(\-?[\d]+[.,]?\d*)', text, re.IGNORECASE)
        if answer_match:
            answer = answer_match.group(1)
            # Extract explanation
            expl_match = re.search(r'EXPLANATION:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
            if expl_match:
                explanation = expl_match.group(1).strip()
        
        if not answer:
            # Method 1: Try to find JSON format
            json_match = re.search(r'\{[^}]*"answer"\s*:\s*"?([^"}\s]+)"?[^}]*\}', text)
            if json_match:
                raw_answer = json_match.group(1)
                # Keep digits, dots, commas, and minus
                cleaned = re.sub(r'[^0-9.,\-]', '', raw_answer)
                if cleaned:
                    answer = cleaned
            
            # Method 2: Try to find \boxed{...} format
            if not answer:
                boxed_match = re.search(r'\\boxed\{[^}]*?(\-?[\d]+[.,]?\d*)[^}]*\}', text)
                if boxed_match:
                    answer = boxed_match.group(1)
            
            # Method 3: Look for "answer is X" patterns
            if not answer:
                answer_pattern = re.search(r'(?:answer|đáp án|kết quả|result)(?:\s+is|\s+là|:)?\s*[\[\(]?\s*(\-?[\d]+[.,]?\d*)', text, re.IGNORECASE)
                if answer_pattern:
                    answer = answer_pattern.group(1)
            
            # Method 4: If response is very short
            if not answer and len(text) < 20:
                # Extract number with optional decimal
                short_match = re.search(r'(\-?[\d]+[.,]?\d*)', text)
                if short_match:
                    answer = short_match.group(1)
            
            # Method 5: Find the last number (including decimals)
            if not answer:
                all_numbers = re.findall(r'\-?[\d]+[.,]?\d*', text)
                if all_numbers:
                    answer = all_numbers[-1]
        
        # Use full text as explanation if needed
        if with_explanation and not explanation:
            explanation = text
        
        # Convert period to comma for decimal separator
        if answer:
            answer = answer.replace('.', ',')
            if with_explanation:
                return (answer, explanation)
            return answer
        
        print(f"Could not find answer in response")
        return (None, None) if with_explanation else None
            
    except Exception as e:
        print(f"Error calling Gemini API (Short Answer): {e}")
        return (None, None) if with_explanation else None

# ==========================================
# MAIN LOGIC
# ==========================================

def main():
    if not configure_gemini():
        return

    driver = setup_driver()
    if not driver:
        print("Failed to initialize WebDriver.")
        return

    try:
        print(f"Opening {TARGET_URL}...")
        driver.get(TARGET_URL)
        
        print("\n" + "="*50)
        print("PLEASE LOG IN AND NAVIGATE TO THE QUIZ PAGE.")
        print("Once the first question is visible, press ENTER in this terminal to start automation.")
        print("="*50 + "\n")
        input("Press Enter to start...")

        while True:
            print("\n--- Processing Question ---")
            
            # 1. Find Question Content and Screenshot
            try:
                # Wait for question to load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".question-name"))
                )
                
                # Take full page screenshot to capture question and all options
                screenshot_png = driver.get_screenshot_as_png()
                image_data = screenshot_png
                print("Captured full page screenshot.")

            except TimeoutException:
                print("Timed out waiting for question. Quiz might be finished.")
                break
            except Exception as e:
                print(f"Error extracting question: {e}")
                break

            # 2. Detect question type: Short Answer, True/False, or Multiple Choice
            # Check for SHORT ANSWER first (input fields for numeric answers)
            short_answer_inputs = driver.find_elements(By.CSS_SELECTOR, ".answer-input input[type='text']")
            if not short_answer_inputs:
                # Also try finding by ID pattern
                short_answer_inputs = driver.find_elements(By.CSS_SELECTOR, "input[id^='mathplay-answer']")
            
            true_false_containers = driver.find_elements(By.CSS_SELECTOR, ".true-false")
            
            if short_answer_inputs:
                # =============================================
                # SHORT ANSWER QUESTION TYPE
                # =============================================
                print(f"Detected SHORT ANSWER question with {len(short_answer_inputs)} input field(s).")
                
                # Get answer from Gemini
                answer = get_short_answer_response(image_data)
                
                if answer:
                    print(f"Gemini calculated answer: {answer}")
                    
                    # Type the answer into the first input field
                    try:
                        input_field = short_answer_inputs[0]
                        
                        # Scroll into view
                        driver.execute_script("arguments[0].scrollIntoView(true);", input_field)
                        time.sleep(0.3)
                        
                        # Clear existing value and type new answer
                        input_field.clear()
                        input_field.send_keys(answer)
                        
                        print(f"Typed answer: '{answer}' into input field.")
                        time.sleep(1)
                        
                    except Exception as e:
                        print(f"Error typing answer: {e}")
                else:
                    print("Could not get answer from Gemini. Skipping.")
                    
            elif true_false_containers:
                # =============================================
                # TRUE/FALSE QUESTION TYPE
                # =============================================
                print(f"Detected TRUE/FALSE question with {len(true_false_containers)} statements.")
                
                # Get answers from Gemini
                answers = get_true_false_response(image_data, len(true_false_containers))
                
                if answers and len(answers) >= len(true_false_containers):
                    for idx, tf_container in enumerate(true_false_containers):
                        answer = answers[idx] if idx < len(answers) else "true"
                        letter = chr(ord('a') + idx)
                        
                        try:
                            # Find the radio buttons in this container
                            # Radio inputs are often hidden, so we need to click the label instead
                            if answer == "true":
                                radio = tf_container.find_element(By.CSS_SELECTOR, "input[value='true']")
                                label_text = "Đúng"
                            else:
                                radio = tf_container.find_element(By.CSS_SELECTOR, "input[value='false']")
                                label_text = "Sai"
                            
                            # Get the radio's ID and find its label
                            radio_id = radio.get_attribute("id")
                            
                            # Scroll into view
                            driver.execute_script("arguments[0].scrollIntoView(true);", radio)
                            time.sleep(0.3)
                            
                            # Method 1: Try clicking the label by 'for' attribute
                            try:
                                label = tf_container.find_element(By.CSS_SELECTOR, f"label[for='{radio_id}']")
                                label.click()
                                print(f"  Statement {letter}: selected '{label_text}' (via label)")
                            except:
                                # Method 2: Use JavaScript to click the radio directly
                                driver.execute_script("arguments[0].click();", radio)
                                print(f"  Statement {letter}: selected '{label_text}' (via JS)")
                            
                        except Exception as e:
                            print(f"  Error selecting answer for statement {letter}: {e}")
                    
                    print(f"Completed True/False question. Waiting 2 seconds...")
                    time.sleep(2)
                else:
                    print(f"Invalid True/False answers from Gemini: {answers}. Skipping.")
                    
            else:
                # =============================================
                # MULTIPLE CHOICE QUESTION TYPE (A/B/C/D)
                # =============================================
                # Find Options elements to click
                try:
                    options_elems = driver.find_elements(By.CSS_SELECTOR, ".question-option")
                    if not options_elems:
                        print("No options found. Stopping.")
                        break
                    
                    print(f"Detected MULTIPLE CHOICE with {len(options_elems)} options.")
                    
                    # Debug: print option texts
                    for i, opt in enumerate(options_elems):
                        opt_text = opt.text[:50] if opt.text else "(no text)"
                        print(f"  Option {chr(65+i)}: {opt_text}...")

                except Exception as e:
                    print(f"Error extracting options: {e}")
                    break

                # Get Answer from Gemini (returns A/B/C/D)
                answer_letter = get_gemini_response(image_data)
                
                if answer_letter and answer_letter in "ABCD":
                    print(f"Gemini selected Option: {answer_letter}")
                    
                    # Click Answer directly on the option element
                    answer_index = ord(answer_letter) - ord('A')  # A=0, B=1, C=2, D=3
                    
                    if answer_index < len(options_elems):
                        try:
                            target_option = options_elems[answer_index]
                            
                            # Scroll into view and click
                            driver.execute_script("arguments[0].scrollIntoView(true);", target_option)
                            time.sleep(0.5)
                            
                            # Try regular click first
                            try:
                                target_option.click()
                            except ElementClickInterceptedException:
                                # If blocked, use JavaScript click
                                driver.execute_script("arguments[0].click();", target_option)
                            
                            print(f"Clicked option {answer_letter}. Waiting 4 seconds...")
                            time.sleep(4)  # Wait for "Trả lời" button to appear
                            
                        except Exception as e:
                            print(f"Error clicking option: {e}")
                    else:
                        print(f"Answer index {answer_index} out of range for {len(options_elems)} options.")
                else:
                    print(f"Invalid answer from Gemini: {answer_letter}. Skipping.")

            # 5. Navigate to Next Question
            # DEBUG: Print all visible buttons to find the correct selector
            print("\n--- DEBUG: All buttons on page ---")
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            for i, btn in enumerate(all_buttons):
                try:
                    btn_text = btn.text.strip()
                    btn_class = btn.get_attribute("class")
                    btn_visible = btn.is_displayed()
                    if btn_visible and btn_text:
                        print(f"  Button {i}: text='{btn_text}', class='{btn_class}'")
                except:
                    pass
            print("--- END DEBUG ---\n")
            
            # Wait for "Trả lời" button (it's a div, not a button!)
            next_buttons_selectors = [
                "//div[contains(@class, 'btn')]//span[contains(text(), 'Trả lời')]/parent::div",  # div > span with "Trả lời"
                "//div[contains(@class, 'btn-primary')]//span[contains(text(), 'Trả lời')]/..",  # Alternative
                "//div[contains(., 'Trả lời') and contains(@class, 'btn')]",  # div with "Trả lời" text
                ".btn-primary",  # CSS fallback
            ]
            
            clicked_next = False
            for selector in next_buttons_selectors:
                try:
                    if selector.startswith("//"):
                        btn = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        btn = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    
                    # Check if this is not "Nộp bài"
                    btn_text = btn.text.strip()
                    if "Nộp bài" in btn_text:
                        print(f"Skipping 'Nộp bài' button...")
                        continue
                    
                    btn.click()
                    clicked_next = True
                    print(f"Clicked 'Trả lời' button with selector: {selector}")
                    time.sleep(2) 
                    break
                except:
                    continue
            
            if not clicked_next:
                print("Could not find 'Trả lời' button!")
                print("Please check the DEBUG output above and tell me what the button text/class is.")
                print("Waiting for user to manually click 'Trả lời', or press Enter to try next question...")
                input("Press Enter after clicking 'Trả lời' manually...")

    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print("Closing driver...")
        driver.quit()

if __name__ == "__main__":
    main()
