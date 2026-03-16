import asyncio
import base64
import threading
import time
import io
import queue
from selenium import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.action_chains import ActionChains

# Thread-safe dictionary to hold active sessions
# Key: session_id (or account_id), Value: BrowserSession object
active_sessions = {}

class BrowserSession:
    def __init__(self, account_id, proxy_info=None):
        self.account_id = account_id
        self.proxy_info = proxy_info
        self.driver = None
        self.lock = threading.Lock()
        self.is_solving = False
        self.last_screenshot = None
        self.stop_event = threading.Event()
        self.command_queue = queue.Queue()

    def start_browser(self):
        """Starts the Chrome instance"""
        try:
            print(f"Starting Chrome for {self.account_id}...")
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            # options.add_argument("--headless=new") # Optional: Uncomment for true background
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            if self.proxy_info:
                pass 
                
            self.driver = uc.Chrome(options=options, version_main=142)
            self.driver.get("https://app.onluyen.vn")
            print(f"Chrome started for {self.account_id}")
            
            # Start screenshot loop
            threading.Thread(target=self._screenshot_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"Error starting browser: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _screenshot_loop(self):
        """Continously captures screenshots for streaming"""
        while not self.stop_event.is_set():
            if self.driver:
                try:
                    # Capture Base64
                    b64 = self.driver.get_screenshot_as_base64()
                    self.last_screenshot = b64
                except:
                    pass
            time.sleep(0.1) # 10 FPS max

    def stream_frame(self):
        """Yields MJPEG frames"""
        while not self.stop_event.is_set():
            if self.last_screenshot:
                # Convert base64 to bytes
                data = base64.b64decode(self.last_screenshot)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + data + b'\r\n')
            time.sleep(0.1)

    def handle_input(self, action_type, data):
        """Handles input from Frontend if not solving"""
        if self.is_solving:
            return # Block input
            
        with self.lock:
            if not self.driver: return
            
            try:
                if action_type == 'click':
                    x, y = data['x'], data['y']
                    # Calculate position relative to browser? 
                    # Complex mapping needed if image is resized in frontend.
                    # Assuming 1:1 for now or handled by frontend sending relative %
                    
                    # ActionChains(self.driver).move_by_offset(x, y).click().perform()
                    # Better: define a "body" element and move relative to it?
                    # Or simpler: Execute JS
                    self.driver.execute_script(f"document.elementFromPoint({x}, {y}).click();")
                    
                elif action_type == 'type':
                    text = data['text']
                    ActionChains(self.driver).send_keys(text).perform()
            except Exception as e:
                print(f"Input error: {e}")

    def start_solving_task(self):
        """Starts the solver engine in a separate thread"""
        if self.is_solving: return
        
        from .solver_service import SolverEngine # Import here to avoid circular
        self.is_solving = True
        self.solver = SolverEngine(self)
        threading.Thread(target=self.solver.solve_loop, daemon=True).start()

    def stop_solving_task(self):
        if self.is_solving and self.solver:
            self.solver.stop()
        self.is_solving = False
        self.solver = None

class BrowserManager:
    @staticmethod
    def create_session(account_id, proxy=None):
        session = BrowserSession(account_id, proxy)
        if session.start_browser():
            active_sessions[account_id] = session
            return True
        return False
        
    @staticmethod
    def get_session(account_id):
        return active_sessions.get(account_id)
