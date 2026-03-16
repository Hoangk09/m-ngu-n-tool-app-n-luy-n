import google.generativeai as genai
import time
import base64
import io
from PIL import Image
import threading
import asyncio
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# Gemini Config (Should be loaded from DB/Config per user or global)
API_KEY = "YOUR_GEMINI_KEY" # Placeholder
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

class SolverEngine:
    """
    Handles the automation logic for a single browser session.
    Controls the driver to Navigate -> Screenshot -> Solve -> Click -> Repeat.
    """
    
    def __init__(self, browser_session):
        self.session = browser_session
        self.driver = browser_session.driver
        self.stop_flag = False
        
    def solve_loop(self):
        """Main loop runs in a thread"""
        print(f"Starting solver for {self.session.account_id}")
        
        while not self.stop_flag and self.session.is_solving:
            try:
                # 1. Check if we are on a question page
                # Simple check: Look for answer buttons A/B/C/D or similar
                # Or just capture and ask AI
                
                # Capture screenshot
                if not self.driver: break
                
                # Wait for page load logic here if needed
                time.sleep(2) 
                
                screenshot_b64 = self.driver.get_screenshot_as_base64()
                img = Image.open(io.BytesIO(base64.b64decode(screenshot_b64)))
                
                # 2. Ask Gemini
                # We reuse the logic from quiz_solver.py
                prompt = "Solve this multiple choice question. Return only the letter A, B, C, or D."
                try:
                    response = model.generate_content([prompt, img])
                    answer = response.text.strip().upper()
                    # Clean answer
                    import re # Lazy import
                    match = re.search(r'[ABCD]', answer)
                    if match:
                        answer = match.group()
                    print(f"Gemini Answer: {answer}")
                except Exception as e:
                    print(f"Gemini Error: {e}")
                    continue
                
                # 3. Click Answer
                if answer in ['A', 'B', 'C', 'D']:
                    self.click_answer(answer)
                
                # 4. Navigate Next
                self.click_next()
                
                # Rate limit
                time.sleep(3)
                
            except Exception as e:
                print(f"Solver loop error: {e}")
                time.sleep(5)

    def click_answer(self, letter):
        # Implementation from quiz_solver_app.py
        try:
            # Re-find elements to avoid stale reference
             # Assumes .question-option structure
             options_elems = self.driver.find_elements(By.CSS_SELECTOR, ".question-option")
             
             # Map letter to index
             answer_index = ord(letter) - ord('A')
             
             if answer_index < len(options_elems):
                 target = options_elems[answer_index]
                 # Scroll view
                 self.driver.execute_script("arguments[0].scrollIntoView(true);", target)
                 time.sleep(0.3)
                 try:
                     target.click()
                 except:
                     self.driver.execute_script("arguments[0].click();", target)
        except Exception as e:
            print(f"Click error: {e}")

    def click_next(self):
        try:
            # Logic from app: find "Câu sau" or next button
            # Trying common selectors
            next_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Câu sau') or contains(text(), 'Next')]")
            if next_btns:
                next_btns[0].click()
            else:
                # Try finding by class or ID common in Onluyen
                pass
        except Exception as e:
            print(f"Next error: {e}")
            
    def stop(self):
        self.stop_flag = True
