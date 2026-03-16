import threading
import time
import io
import base64
import random
import requests
import socket
import subprocess
import os
import signal
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from werkzeug.security import check_password_hash
from models import db, SolverSession
from datetime import datetime
import google.generativeai as genai

class VNCManager:
    """Manages Xvfb and x11vnc for each session"""
    
    _next_display = 10  # Start from display :10
    _used_displays = set()
    _next_vnc_port = 5910  # VNC port = 5900 + display number
    
    @classmethod
    def get_next_display(cls):
        display = cls._next_display
        while display in cls._used_displays:
            display += 1
        cls._used_displays.add(display)
        cls._next_display = display + 1
        return display
    
    @classmethod
    def release_display(cls, display):
        cls._used_displays.discard(display)


class VNCSession:
    """Manages Xvfb + x11vnc for a single browser session"""
    
    def __init__(self, session_id):
        self.session_id = session_id
        self.display = VNCManager.get_next_display()
        self.display_str = f":{self.display}"
        self.vnc_port = 5900 + self.display
        self.websocket_port = 6080 + self.display - 10  # noVNC websocket port
        self.xvfb_proc = None
        self.x11vnc_proc = None
        self.websockify_proc = None
        
    def start(self):
        """Start Xvfb, x11vnc, and websockify"""
        try:
            # Start Xvfb (virtual display)
            self.xvfb_proc = subprocess.Popen(
                ['Xvfb', self.display_str, '-screen', '0', '1920x1080x24'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(1)
            
            # Start x11vnc (VNC server)
            self.x11vnc_proc = subprocess.Popen(
                ['x11vnc', '-display', self.display_str, 
                 '-forever', '-nopw', '-shared', 
                 '-rfbport', str(self.vnc_port),
                 '-bg', '-o', '/dev/null'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(1)
            
            # Start websockify (WebSocket proxy for noVNC)
            self.websockify_proc = subprocess.Popen(
                ['websockify', '--web=/usr/share/novnc/', 
                 str(self.websocket_port), f'localhost:{self.vnc_port}'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            print(f"[VNC] Started display {self.display_str}, VNC:{self.vnc_port}, WebSocket:{self.websocket_port}")
            return True
        except Exception as e:
            print(f"[VNC] Error starting: {e}")
            return False
    
    def stop(self):
        """Stop all VNC processes"""
        for proc in [self.websockify_proc, self.x11vnc_proc, self.xvfb_proc]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except:
                    try:
                        proc.kill()
                    except:
                        pass
        VNCManager.release_display(self.display)
        print(f"[VNC] Stopped display {self.display_str}")
    
    def get_display_env(self):
        """Return the DISPLAY environment variable for Chrome"""
        return self.display_str
    
    def get_novnc_url(self):
        """Return the noVNC URL for embedding"""
        return f"/vnc/?port={self.websocket_port}"


class WebSolverManager:
    _sessions = {} # session_id -> SolverInstance

    @classmethod
    def start_session(cls, app, session_id, account_data, config=None):
        instance = SolverInstance(app, session_id, account_data, config)
        cls._sessions[session_id] = instance
        instance.start()
        return instance

    @classmethod
    def get_session(cls, session_id):
        return cls._sessions.get(session_id)
    
    @classmethod
    def cleanup(cls, session_id):
        if session_id in cls._sessions:
            cls._sessions[session_id].stop()
            del cls._sessions[session_id]


class SolverInstance:
    def __init__(self, app, session_id, account_data, config):
        self.app = app
        self.session_id = session_id
        self.account = account_data
        self.driver = None
        self.running = False
        self.current_frame = None
        self.logs = []
        self.state = 'INIT'
        self.selected_assignment = None
        self.vnc_session = None
        
    def start(self):
        self.running = True
        threading.Thread(target=self._init_and_login, daemon=True).start()
        
    def stop(self):
        self.running = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        if self.vnc_session:
            self.vnc_session.stop()
        
    def get_frame(self):
        """Return screenshot as PNG bytes"""
        if self.driver:
            try:
                return self.driver.get_screenshot_as_png()
            except:
                pass
        return None
    
    def get_vnc_url(self):
        """Get the noVNC URL for this session"""
        if self.vnc_session:
            return self.vnc_session.get_novnc_url()
        return None
    
    def get_websocket_port(self):
        """Get the websocket port for noVNC"""
        if self.vnc_session:
            return self.vnc_session.websocket_port
        return None

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        self.logs.append(line)
        print(f"[Session {self.session_id}] {message}")

    def _init_and_login(self):
        """Phase 1: Initialize VNC, browser and login"""
        with self.app.app_context():
            try:
                # Start VNC session
                self.log("Starting VNC display...")
                self.vnc_session = VNCSession(self.session_id)
                if not self.vnc_session.start():
                    self.log("Failed to start VNC, falling back to headless")
                    self.vnc_session = None
                
                self.log("Initializing Chrome...")
                
                options = uc.ChromeOptions()
                options.add_argument("--start-maximized")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                
                # Set DISPLAY environment for VNC - MUST set os.environ directly
                if self.vnc_session:
                    os.environ['DISPLAY'] = self.vnc_session.get_display_env()
                    self.log(f"Using display {os.environ['DISPLAY']}")
                
                # Start Chrome with the VNC display
                self.driver = uc.Chrome(options=options)
                self.log("Opening App Onluyen...")
                self.driver.get("https://app.onluyen.vn/")
                
                # Login
                self._do_login()
                
                # Wait for homepage to load
                time.sleep(3)
                self.state = 'LOGGED_IN'
                self.log("✅ Ready to select assignment")
                
            except Exception as e:
                self.log(f"Error: {e}")
                import traceback
                self.log(traceback.format_exc())
                self.state = 'ERROR'
                
    def _do_login(self):
        try:
            time.sleep(3)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".form-login"))
            )
            
            user_input = self.driver.find_element(By.CSS_SELECTOR, ".form-login .input-name input[type='text']")
            user_input.clear()
            user_input.send_keys(self.account['username'])
            
            pass_input = self.driver.find_element(By.CSS_SELECTOR, ".form-login .input-name input[type='password']")
            pass_input.clear()
            pass_input.send_keys(self.account['password'])
            
            btn = self.driver.find_element(By.CSS_SELECTOR, ".btn-login button")
            btn.click()
            self.log("Login submitted")
            time.sleep(3)
        except Exception as e:
            self.log(f"Login failed: {e}")
            
    def get_assignments(self):
        """Phase 2: Get list of incomplete assignments"""
        if self.state != 'LOGGED_IN':
            return []
        
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".class-as"))
            )
            
            boxes = self.driver.find_elements(By.CSS_SELECTOR, ".class-as")
            assignments = []
            
            for idx, box in enumerate(boxes):
                try:
                    status_elem = box.find_element(By.CSS_SELECTOR, ".status")
                    status_text = status_elem.text.lower()
                    
                    if any(s in status_text for s in ["đang làm", "chờ làm bài", "chờ làm", "chưa làm", "chưa nộp", "dl", "incomplete", "pending", "in progress"]):
                        name_elem = box.find_element(By.CSS_SELECTOR, ".name-as")
                        name = name_elem.text.strip()
                        
                        assignments.append({
                            "index": idx,
                            "name": name,
                            "status": status_text.strip()
                        })
                except:
                    continue
            return assignments
        except Exception as e:
            self.log(f"Error getting assignments: {e}")
            return []
            
    def select_and_solve(self, assignment_index):
        """Phase 3: Select an assignment and start solving"""
        if self.state != 'LOGGED_IN':
            self.log(f"Cannot select - state is {self.state}")
            return False
        
        self.state = 'SOLVING'
        self.selected_assignment = assignment_index
        threading.Thread(target=self._solve_assignment, args=(assignment_index,), daemon=True).start()
        return True
        
    def _solve_assignment(self, assignment_index):
        """Solve the selected assignment"""
        with self.app.app_context():
            try:
                self.log(f"Looking for assignment #{assignment_index}...")
                
                # Step 1: Find and click the assignment box
                try:
                    boxes = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".class-as"))
                    )
                except:
                    self.log("❌ Could not find assignment boxes (.class-as)")
                    self.state = 'ERROR'
                    return
                    
                if assignment_index >= len(boxes):
                    self.log(f"❌ Invalid index {assignment_index}, only {len(boxes)} assignments found")
                    self.state = 'ERROR'
                    return
                
                # Click the assignment
                self.log(f"Clicking assignment #{assignment_index}...")
                boxes[assignment_index].click()
                time.sleep(3)  # Wait for page transition
                
                # Step 2: Verify we're on the assignment page and find "Bắt đầu" button
                self.log("Looking for 'Bắt đầu' button...")
                try:
                    # Wait for the start button to appear
                    start_btn = WebDriverWait(self.driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn-test.green, .btn.btn-success[onclick*='start'], button.green"))
                    )
                    self.log("✅ Found 'Bắt đầu' button, clicking...")
                    start_btn.click()
                    time.sleep(3)
                except Exception as e:
                    self.log(f"⚠️ Could not find 'Bắt đầu' button: {e}")
                    # Try alternative selectors
                    try:
                        start_btn = self.driver.find_element(By.XPATH, "//button[contains(text(),'Bắt đầu')]")
                        start_btn.click()
                        self.log("✅ Clicked 'Bắt đầu' (via XPath)")
                        time.sleep(3)
                    except:
                        self.log("⚠️ No start button found - may already be in quiz")
                
                # Step 3: Start solving
                self.log("🚀 Starting quiz solver...")
                try:
                    from quiz_logic_advanced import solve_quiz
                    config = dict(self.account)
                    config['auto_detect'] = False
                    solve_quiz(self.driver, config, self.log)
                except ImportError:
                    self.log("❌ Could not import quiz_logic_advanced!")
                except Exception as e:
                    self.log(f"❌ Solver Error: {e}")
                    import traceback
                    self.log(traceback.format_exc())
                            
            except Exception as e:
                self.log(f"Error: {e}")
                import traceback
                self.log(traceback.format_exc())
            finally:
                self.state = 'DONE'
                self.log("Session complete.")
                sess = SolverSession.query.get(self.session_id)
                if sess:
                    sess.status = 'COMPLETED'
                    sess.end_time = datetime.utcnow()
                    db.session.commit()
