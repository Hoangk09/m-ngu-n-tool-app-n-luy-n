"""
Quiz Solver Multi-Account Advanced - Run multiple accounts simultaneously
Features:
1. Each Chrome: separate Gemini API key
2. Proxy rotation from proxyxoay.shop (auth -> local bridge)
3. Local proxy bridge (converts auth -> non-auth)
4. Auto-detect incomplete assignments
5. Answer caching with backend
6. 60-second proxy rotation delay
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import json
import os
import time
import random
import requests
import socket
from datetime import datetime
from pathlib import Path
import sys
from hashlib import md5

# Selenium imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
import undetected_chromedriver as uc

# Gemini
import google.generativeai as genai

# Config
def get_app_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

APP_DIR = get_app_path()
CONFIG_FILE = APP_DIR / "multi_config.json"


class LocalProxyBridge:
    """Local proxy server that converts auth proxy to non-auth for Chrome"""
    
    def __init__(self, proxy_auth, port=0):
        """
        Initialize local proxy bridge
        :param proxy_auth: Auth proxy in format 'user:pass@ip:port'
        :param port: Port to listen on (0 = find free port automatically)
        """
        self.proxy_auth = proxy_auth
        self.port = port
        self.socket = None
        self.thread = None
        self.running = False
        
    def start(self):
        """Start listening on local port"""
        try:
            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to localhost
            self.socket.bind(('127.0.0.1', self.port))
            
            # Get actual port if we used 0
            if self.port == 0:
                self.port = self.socket.getsockname()[1]
            
            # Listen for connections
            self.socket.listen(5)
            self.running = True
            
            # Start handling connections in background thread
            self.thread = threading.Thread(target=self._accept_connections, daemon=True)
            self.thread.start()
            
            return True
        except Exception as e:
            print(f"Error starting proxy bridge: {e}")
            return False
    
    def _accept_connections(self):
        """Accept and forward connections through auth proxy"""
        while self.running:
            try:
                client_socket, client_addr = self.socket.accept()
                
                # Handle connection in separate thread to avoid blocking
                handler_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                )
                handler_thread.start()
                
            except Exception as e:
                if self.running:
                    pass  # Silently ignore errors when stopping
    
    def _handle_client(self, client_socket):
        """Handle individual client connection and forward through proxy"""
        try:
            # Receive request from Chrome
            request_data = b''
            while len(request_data) < 4096:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                request_data += chunk
                
                # Check if we have complete HTTP request headers
                if b'\r\n\r\n' in request_data:
                    break
            
            if not request_data:
                client_socket.close()
                return
            
            # Parse request to get target host
            try:
                request_str = request_data.decode('utf-8', errors='ignore')
                lines = request_str.split('\r\n')
                
                if not lines:
                    client_socket.close()
                    return
                
                # Get CONNECT method (for HTTPS tunneling) or HTTP method
                request_line = lines[0]
                parts = request_line.split()
                
                if len(parts) < 2:
                    client_socket.close()
                    return
                
                method = parts[0]
                target = parts[1]
                
                # For CONNECT method (HTTPS), establish tunnel
                if method == 'CONNECT':
                    # Extract host:port from CONNECT request
                    try:
                        target_host, target_port = target.split(':')
                        target_port = int(target_port)
                    except:
                        client_socket.close()
                        return
                    
                    # Connect to target through auth proxy
                    if self._establish_tunnel(client_socket, target_host, target_port):
                        pass  # Tunnel established and handled
                else:
                    # For HTTP method, forward request through proxy
                    self._forward_http(client_socket, request_data)
                    
            except Exception as e:
                pass
            finally:
                client_socket.close()
                
        except Exception as e:
            pass
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    def _establish_tunnel(self, client_socket, target_host, target_port):
        """Establish CONNECT tunnel through proxy"""
        try:
            # Parse proxy auth credentials
            proxy_parts = self.proxy_auth.split('@')
            if len(proxy_parts) != 2:
                return False
            
            auth_part = proxy_parts[0]
            proxy_addr = proxy_parts[1]
            
            user, password = auth_part.split(':', 1)
            proxy_host, proxy_port = proxy_addr.split(':')
            proxy_port = int(proxy_port)
            
            # Connect to proxy
            proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy_socket.connect((proxy_host, proxy_port))
            
            # Send proxy authentication (if needed)
            # Basic auth: base64(user:pass)
            import base64
            auth_str = base64.b64encode(f"{user}:{password}".encode()).decode()
            
            # Send CONNECT request to proxy
            connect_request = f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
            connect_request += "Host: " + target_host + "\r\n"
            connect_request += f"Proxy-Authorization: Basic {auth_str}\r\n"
            connect_request += "Connection: keep-alive\r\n"
            connect_request += "\r\n"
            
            proxy_socket.sendall(connect_request.encode())
            
            # Read response from proxy
            response = proxy_socket.recv(1024)
            
            # Check if connection established (200 response)
            if b'200' not in response:
                proxy_socket.close()
                return False
            
            # Send success response to client
            client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            
            # Relay data between client and proxy (bidirectional forwarding)
            self._relay_data(client_socket, proxy_socket)
            
            return True
            
        except Exception as e:
            return False
    
    def _forward_http(self, client_socket, request_data):
        """Forward HTTP request through proxy"""
        try:
            # Parse proxy auth
            proxy_parts = self.proxy_auth.split('@')
            if len(proxy_parts) != 2:
                return
            
            auth_part = proxy_parts[0]
            proxy_addr = proxy_parts[1]
            
            user, password = auth_part.split(':', 1)
            proxy_host, proxy_port = proxy_addr.split(':')
            proxy_port = int(proxy_port)
            
            # Connect to proxy
            proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy_socket.connect((proxy_host, proxy_port))
            
            # Send request to proxy
            proxy_socket.sendall(request_data)
            
            # Receive response from proxy
            response = b''
            while True:
                try:
                    chunk = proxy_socket.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                except socket.timeout:
                    break
            
            # Send response back to client
            client_socket.sendall(response)
            proxy_socket.close()
            
        except Exception as e:
            pass
    
    def _relay_data(self, client_socket, proxy_socket):
        """Relay data bidirectionally between client and proxy"""
        def forward(source, destination):
            try:
                while True:
                    data = source.recv(4096)
                    if not data:
                        break
                    destination.sendall(data)
            except:
                pass
            finally:
                try:
                    source.close()
                except:
                    pass
        
        # Create threads for bidirectional forwarding
        thread1 = threading.Thread(target=forward, args=(client_socket, proxy_socket), daemon=True)
        thread2 = threading.Thread(target=forward, args=(proxy_socket, client_socket), daemon=True)
        
        thread1.start()
        thread2.start()
        
        # Wait for threads
        thread1.join()
        thread2.join()
    
    def stop(self):
        """Stop listening and close"""
        self.running = False
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
    
    def get_url(self):
        """Get the local proxy URL for Chrome"""
        return f"http://127.0.0.1:{self.port}"


class ProxyRotator:
    """Manage rotating proxy from proxyxoay.shop with auth -> non-auth conversion"""
    
    def __init__(self, proxy_key, log_callback):
        self.proxy_key = proxy_key
        self.log = log_callback
        self.proxy_auth = None  # user:pass@ip:port (for LocalProxyBridge)
        self.proxy_noauth = None  # ip:port (no auth)
        self.base_url = "https://proxyxoay.shop/api/get.php"
        
    def get_proxy(self):
        """Get proxy (fetch from API each time)"""
        self._fetch_new_proxy()
        # Return auth proxy for LocalProxyBridge (user:pass@ip:port)
        return self.proxy_auth
    
    def _fetch_new_proxy(self):
        """Fetch new proxy from proxyxoay.shop API"""
        self.log("🔄 [ProxyRotator] Fetching new proxy from API...")
        try:
            params = {
                "key": self.proxy_key,
                "nhamang": "Được liệt kê bên dưới",
                "tinhthành": "0.Random"
            }
            
            self.log(f"🔄 [ProxyRotator] Calling API: {self.base_url}")
            response = requests.get(self.base_url, params=params, timeout=10)
            self.log(f"🔄 [ProxyRotator] API response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"🔄 [ProxyRotator] API response data: {data}")
                
                if data.get("status") == 100:
                    # Try multiple proxy formats from API response
                    proxy_str = None
                    
                    # Format 1: proxyhttp (ip:port::)
                    if "proxyhttp" in data:
                        proxy_str = data.get("proxyhttp", "").strip()
                        self.log(f"📦 Found proxyhttp: {proxy_str}")
                    
                    # Format 2: proxysocks5 (if no http)
                    if not proxy_str and "proxysocks5" in data:
                        proxy_str = data.get("proxysocks5", "").strip()
                        self.log(f"📦 Found proxysocks5: {proxy_str}")
                    
                    # Format 3: proxy field (if neither)
                    if not proxy_str and "proxy" in data:
                        proxy_str = data.get("proxy", "").strip()
                        self.log(f"📦 Found proxy: {proxy_str}")
                    
                    if proxy_str:
                        # Parse: ip:port:: or ip:port:user:pass
                        parts = proxy_str.split(":")
                        self.log(f"📦 Raw proxy format: {proxy_str}")
                        self.log(f"📦 Parts: {parts} (count: {len(parts)})")
                        
                        if len(parts) >= 2:
                            ip = parts[0].strip()
                            port = parts[1].strip()
                            
                            # Check if has credentials
                            if len(parts) >= 4 and parts[2].strip() and parts[3].strip():
                                user = parts[2].strip()
                                password = parts[3].strip()
                                self.log(f"✅ Proxy with auth: {ip}:{port} | user: {user}")
                                self.proxy_auth = f"{user}:{password}@{ip}:{port}"
                            else:
                                # No credentials, proxy is public/free
                                self.log(f"✅ Proxy without auth (public): {ip}:{port}")
                                self.proxy_auth = None  # Cannot use with LocalProxyBridge
                            
                            self.proxy_noauth = f"{ip}:{port}"
                            self.log(f"✅ proxy_auth: {self.proxy_auth}")
                            self.log(f"✅ proxy_noauth: {self.proxy_noauth}")
                            return True
                        else:
                            self.log(f"❌ Format invalid! Expected at least ip:port")
                            return False
                    else:
                        self.log(f"❌ No proxy found in API response")
                        return False
                else:
                    error_msg = data.get('message', 'Unknown error')
                    self.log(f"❌ Proxy API error: status={data.get('status')}, msg={error_msg}")
                    return False
            else:
                self.log(f"❌ API HTTP error: {response.status_code}")
                return False
                    
        except Exception as e:
            self.log(f"❌ Lỗi fetch proxy: {type(e).__name__}: {e}")
            import traceback
            self.log(f"   Traceback: {traceback.format_exc()}")
            return False


class AnswerFileManager:
    """Manage answer files from backend"""
    
    def __init__(self, backend_url, log_callback):
        self.backend_url = backend_url
        self.log = log_callback
    
    def get_answer_file(self, quiz_name):
        """Get answer file from backend"""
        try:
            quiz_hash = md5(quiz_name.encode()).hexdigest()
            response = requests.post(
                f"{self.backend_url}/api/get-answer-file",
                json={"quiz_name": quiz_name, "quiz_hash": quiz_hash},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("answers"):
                    return data.get("answers")
            return None
        except:
            return None
    
    def save_answers(self, quiz_name, answers_dict):
        """Save answers to backend"""
        try:
            payload = {
                "quiz_name": quiz_name,
                "quiz_hash": md5(quiz_name.encode()).hexdigest(),
                "answers": answers_dict,
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(
                f"{self.backend_url}/api/save-answer-file",
                json=payload,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False


class AssignmentDetector:
    """Detect incomplete assignments on homepage"""
    
    def __init__(self, driver):
        self.driver = driver
    
    def get_incomplete_assignments(self):
        """Find incomplete assignments"""
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".class-as"))
            )
            
            boxes = self.driver.find_elements(By.CSS_SELECTOR, ".class-as")
            assignments = []
            
            for box in boxes:
                try:
                    status_elem = box.find_element(By.CSS_SELECTOR, ".status")
                    status_text = status_elem.text.lower()
                    
                    if any(s in status_text for s in ["chờ làm", "chưa làm", "dl", "incomplete"]):
                        name_elem = box.find_element(By.CSS_SELECTOR, ".name-as")
                        assignments.append({
                            "name": name_elem.text.strip(),
                            "url": "", # No URL in this mode, click element directly
                            "element": box
                        })
                except:
                    continue
            
            return assignments
        except:
            return []

class AccountWorker:
    """Worker thread for each account with proxy rotation and per-account API key"""
    
    def __init__(self, account_data, log_callback, status_callback, settings):
        self.account = account_data
        self.log = log_callback
        self.status = status_callback
        self.settings = settings
        self.driver = None
        self.running = False
        self.stop_flag = False
        self.browser_ready = False
        self.detected_assignments = []
        self.selected_quiz_name = ""
        
        # Managers
        self.proxy_rotator = None
        self.proxy_bridge = None
        self.answer_manager = None
        
    def open_browser(self):
        """Open browser and login in thread"""
        threading.Thread(target=self._open_browser, daemon=True).start()
    
    def open_browser_sync(self):
        """Open browser synchronously (waits for it to be ready)"""
        self._open_browser()
        
    def start_solving(self):
        """Start quiz solving in thread"""
        if not self.browser_ready:
            name = self.account.get('name', 'Unknown')
            self.log(f"[{name}] ⚠️ Chưa mở Chrome!")
            return
        self.running = True
        self.stop_flag = False
        threading.Thread(target=self._run_solving, daemon=True).start()
        
    def stop(self):
        """Stop automation but keep Chrome running"""
        self.stop_flag = True
        self.running = False
        
        # Cleanup proxy bridge
        if self.proxy_bridge:
            try:
                self.proxy_bridge.stop()
                self.proxy_bridge = None
            except:
                pass
        
        # Do NOT close driver - keep Chrome running for user
        
    def _open_browser(self):
        """Open Chrome and login with proxy rotation support (via local bridge)"""
        name = self.account.get('name', 'Unknown')
        username = self.account.get('username', '')
        password = self.account.get('password', '')
        proxy_key = self.account.get('proxy_key', '').strip()
        api_key = self.account.get('api_key', '')
        backend_url = self.settings.get('backend_url', 'http://localhost:8000')
        
        try:
            self.log(f"[{name}] 🌐 Khởi động Chrome...")
            self.status(name, "🟡 Đang khởi động...")
            
            # Debug: show proxy key status
            if not proxy_key:
                self.log(f"[{name}] ⚠️ Chưa cấu hình proxy_key, sẽ dùng kết nối trực tiếp")
            else:
                self.log(f"[{name}] 🔑 proxy_key: {proxy_key[:20]}...")
            
            # Initialize proxy bridge (converts auth proxy to local non-auth)
            self.proxy_bridge = None
            proxy_url = None
            
            if proxy_key:
                try:
                    self.proxy_rotator = ProxyRotator(proxy_key, self.log)
                    proxy_auth = self.proxy_rotator.get_proxy()
                    self.log(f"[{name}] 📌 get_proxy() returned: {proxy_auth}")
                    self.log(f"[{name}] 📌 proxy_noauth: {self.proxy_rotator.proxy_noauth}")
                    
                    # If proxy_auth is available (has credentials), use LocalProxyBridge
                    if proxy_auth:
                        self.log(f"[{name}] 🔒 Proxy auth: {proxy_auth.split('@')[-1]}")
                        
                        # Create local proxy bridge
                        self.proxy_bridge = LocalProxyBridge(proxy_auth, port=0)
                        if self.proxy_bridge.start():
                            proxy_url = self.proxy_bridge.get_url()
                            self.log(f"[{name}] ✅ Local proxy bridge: {proxy_url}")
                        else:
                            self.log(f"[{name}] ❌ Không thể khởi tạo proxy bridge")
                            self.proxy_bridge = None
                    # If only proxy_noauth (public proxy), use directly in Chrome
                    elif self.proxy_rotator.proxy_noauth:
                        proxy_url = f"http://{self.proxy_rotator.proxy_noauth}"
                        self.log(f"[{name}] 🔓 Proxy public (không auth): {self.proxy_rotator.proxy_noauth}")
                        self.log(f"[{name}] ✅ Sẽ dùng proxy: {proxy_url}")
                    else:
                        self.log(f"[{name}] ❌ API không trả về proxy nào")
                except Exception as proxy_error:
                    self.log(f"[{name}] ❌ Proxy error: {type(proxy_error).__name__}: {proxy_error}")
                    import traceback
                    self.log(f"[{name}] {traceback.format_exc()}")
                    self.proxy_rotator = None
                    self.proxy_bridge = None
            
            # Initialize answer manager
            self.answer_manager = AnswerFileManager(backend_url, self.log)
            
            # Setup Chrome
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            # Profile directory
            profile_path = APP_DIR / "profiles" / name.replace(" ", "_")
            profile_path.mkdir(parents=True, exist_ok=True)
            options.add_argument(f"--user-data-dir={profile_path}")
            
            # Add proxy if bridge is available
            if proxy_url:
                try:
                    options.add_argument(f"--proxy-server={proxy_url}")
                    self.log(f"[{name}] ✅ Chrome sẽ dùng local bridge: {proxy_url}")
                except Exception as e:
                    self.log(f"[{name}] ⚠️ Proxy config lỗi: {e}")
            else:
                self.log(f"[{name}] 🌐 Kết nối trực tiếp (không proxy)")
            
            self.driver = uc.Chrome(options=options)
            self.driver.get("https://app.onluyen.vn/")
            self.log(f"[{name}] ✅ Đã mở Chrome!")
            
            # Auto login
            if username and password:
                self._do_login(name, username, password)
            
            self.browser_ready = True
            self.status(name, "🟢 Sẵn sàng")
            self.log(f"[{name}] 📌 Hãy mở quiz rồi bấm 'Bắt Đầu Giải'")
            
        except Exception as e:
            self.log(f"[{name}] ❌ Lỗi: {e}")
            self.status(name, "🔴 Lỗi")
            
    def _run_solving(self):
        """Run quiz solving with per-account API key"""
        name = self.account.get('name', 'Unknown')
        api_key = self.account.get('api_key', '')
        
        try:
            if not api_key:
                self.log(f"[{name}] ❌ Chưa có Gemini API Key cho account này!")
                self.status(name, "🔴 Chưa có API Key")
                return
            
            # Configure Gemini with account-specific key
            genai.configure(api_key=api_key)
            
            # Run automation
            self._run_automation(name)
            
        except Exception as e:
            self.log(f"[{name}] ❌ Lỗi: {e}")
            self.status(name, "🔴 Lỗi")
        finally:
            self.running = False
    
    def detect_assignments(self):
        """Detect incomplete assignments"""
        name = self.account.get('name', 'Unknown')
        if not self.browser_ready:
            self.log(f"[{name}] ⚠️ Chưa mở Chrome!")
            return
        
        self.log(f"[{name}] 🔍 Tìm bài chưa làm...")
        threading.Thread(target=self._do_detect_assignments, daemon=True).start()
    
    def _do_detect_assignments(self):
        """Detect assignments in background"""
        name = self.account.get('name', 'Unknown')
        try:
            detector = AssignmentDetector(self.driver)
            assignments = detector.get_incomplete_assignments()
            self.detected_assignments = assignments
            
            if assignments:
                self.log(f"[{name}] ✅ Tìm thấy {len(assignments)} bài chưa làm:")
                for i, assignment in enumerate(assignments, 1):
                    self.log(f"[{name}]   {i}. {assignment['name']}")
            else:
                self.log(f"[{name}] ⚠️ Không tìm thấy bài chưa làm")
        except Exception as e:
            self.log(f"[{name}] ❌ Lỗi tìm bài: {e}")
            
    def _do_login(self, name, username, password):
        """Auto login for this account"""
        try:
            time.sleep(3)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".form-login"))
            )
            
            username_field = self.driver.find_element(
                By.CSS_SELECTOR, ".form-login .input-name input[type='text']"
            )
            username_field.clear()
            username_field.send_keys(username)
            
            password_field = self.driver.find_element(
                By.CSS_SELECTOR, ".form-login .input-name input[type='password']"
            )
            password_field.clear()
            password_field.send_keys(password)
            
            login_btn = self.driver.find_element(By.CSS_SELECTOR, ".btn-login button")
            login_btn.click()
            
            time.sleep(4)
            self.log(f"[{name}] ✅ Đã đăng nhập!")
            self.status(name, "🟢 Đã đăng nhập")
            
        except TimeoutException:
            self.log(f"[{name}] ⚠️ Có thể đã đăng nhập sẵn")
        except Exception as e:
            self.log(f"[{name}] ⚠️ Đăng nhập thủ công: {e}")
            
    def _run_automation(self, name):
        """Run quiz automation with all features"""
        from quiz_solver import get_gemini_response, get_true_false_response, get_short_answer_response
        
        delay_min = int(self.settings.get('delay_min', 3))
        delay_max = int(self.settings.get('delay_max', 8))
        quiz_time = int(self.settings.get('quiz_time', 30))
        total_questions = int(self.settings.get('total_questions', 40))
        target_score = float(self.settings.get('target_score', 7.0))
        check_answers = self.settings.get('check_answer_files', True)
        save_answers = self.settings.get('save_answer_files', False)
        auto_detect = self.settings.get('auto_detect', False)
        
        # Auto-detect if enabled
        if auto_detect and self.detected_assignments:
            self.log(f"[{name}] 🔍 Auto-click bài đầu tiên...")
            try:
                first = self.detected_assignments[0]
                if "url" in first:
                    self.driver.get(first["url"])
                    time.sleep(3)
                    self.selected_quiz_name = first.get("name", "")
                    self.log(f"[{name}] ✅ Đã mở: {self.selected_quiz_name}")
            except Exception as e:
                self.log(f"[{name}] ⚠️ Lỗi auto-detect: {e}")
        
        # Calculate correct/wrong distribution
        base_correct = int((target_score * total_questions) / 10)
        variance = random.randint(-1, 1) * max(1, int(total_questions * 0.05))
        correct_needed = max(0, min(total_questions, base_correct + variance))
        wrong_needed = total_questions - correct_needed
        
        question_outcomes = ['correct'] * correct_needed + ['wrong'] * wrong_needed
        random.shuffle(question_outcomes)
        
        start_time = time.time()
        end_time = start_time + (quiz_time * 60)
        question_count = 0
        correct_count = 0
        wrong_count = 0
        last_mouse_move = 0
        
        expected_score = (correct_needed / total_questions) * 10
        
        self.log(f"[{name}] 🚀 Bắt đầu giải bài!")
        self.log(f"[{name}] 📊 Tổng: {total_questions} câu | Mục tiêu: {target_score}đ")
        self.log(f"[{name}] 🎯 Sẽ làm đúng: {correct_needed} câu, sai: {wrong_needed} câu")
        self.log(f"[{name}] 📈 Điểm dự kiến: ~{expected_score:.1f}đ")
        
        # Check answer file if enabled
        answer_file = None
        if check_answers and self.answer_manager:
            try:
                elem = self.driver.find_element(By.CSS_SELECTOR, "h1")
                quiz_name = elem.text.strip()
                answer_file = self.answer_manager.get_answer_file(quiz_name)
                if answer_file:
                    self.log(f"[{name}] ✅ Tìm thấy file đáp án ({len(answer_file.get('questions', []))} câu)!")
            except:
                pass
        
        while not self.stop_flag and time.time() < end_time:
            # Rotate proxy every 60 seconds
            if self.proxy_rotator:
                current_proxy = self.proxy_rotator.get_proxy()
            
            # Fake mouse activity every 5-15 seconds
            if time.time() - last_mouse_move > random.randint(5, 15):
                self._fake_mouse_activity()
                last_mouse_move = time.time()
            
            try:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".question-name"))
                    )
                except TimeoutException:
                    time.sleep(1)
                    continue
                
                question_count += 1
                remaining_time = int((end_time - time.time()) / 60)
                
                # Determine correct or wrong
                if question_count <= len(question_outcomes):
                    should_be_correct = (question_outcomes[question_count - 1] == 'correct')
                else:
                    should_be_correct = True
                
                if should_be_correct:
                    correct_count += 1
                    self.log(f"[{name}] --- Câu {question_count}/{total_questions} | ✅ Đúng (còn {remaining_time}p) ---")
                else:
                    wrong_count += 1
                    self.log(f"[{name}] --- Câu {question_count}/{total_questions} | ❌ Sai (còn {remaining_time}p) ---")
                
                self.status(name, f"🟢 Câu {question_count}/{total_questions}")
                
                # Take screenshot
                image_data = self.driver.get_screenshot_as_png()
                
                # Detect question type
                short_answer_inputs = self.driver.find_elements(By.CSS_SELECTOR, ".answer-input input[type='text']")
                if not short_answer_inputs:
                    short_answer_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[id^='mathplay-answer']")
                true_false_containers = self.driver.find_elements(By.CSS_SELECTOR, ".true-false")
                
                if short_answer_inputs:
                    # SHORT ANSWER
                    self.log(f"[{name}] 📝 Trả lời ngắn")
                    
                    answer_from_file = None
                    if answer_file and should_be_correct:
                        # Try to get answer from file
                        answer_from_file = self._get_answer_from_file(answer_file, question_count, "short_answer")
                    
                    if should_be_correct and answer_from_file:
                        self.log(f"[{name}] 📁 Từ file: {answer_from_file}")
                        input_field = short_answer_inputs[0]
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", input_field)
                        input_field.clear()
                        input_field.send_keys(answer_from_file)
                    elif should_be_correct and not answer_file:
                        result = get_short_answer_response(image_data, with_explanation=True)
                        answer = result[0] if isinstance(result, tuple) else result
                        if answer:
                            self.log(f"[{name}] 💡 Đáp án: {answer}")
                            input_field = short_answer_inputs[0]
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", input_field)
                            input_field.clear()
                            input_field.send_keys(answer)
                    else:
                        random_answer = str(random.randint(1, 100))
                        self.log(f"[{name}] 🎲 Random: {random_answer}")
                        input_field = short_answer_inputs[0]
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", input_field)
                        input_field.clear()
                        input_field.send_keys(random_answer)
                        
                elif true_false_containers:
                    # TRUE/FALSE
                    self.log(f"[{name}] ✅❌ Đúng/Sai ({len(true_false_containers)} câu)")
                    
                    answer_from_file = None
                    if answer_file and should_be_correct:
                        answer_from_file = self._get_answer_from_file(answer_file, question_count, "true_false")
                    
                    if should_be_correct and answer_from_file:
                        answers = [answer_from_file]
                        self.log(f"[{name}] 📁 Từ file: {answer_from_file}")
                    elif should_be_correct and not answer_file:
                        result = get_true_false_response(image_data, len(true_false_containers), with_explanation=True)
                        answers = result[0] if isinstance(result, tuple) else result
                    else:
                        answers = [random.choice(["true", "false"]) for _ in true_false_containers]
                        self.log(f"[{name}] 🎲 Random đáp án...")
                    
                    if answers:
                        for idx, tf_container in enumerate(true_false_containers):
                            answer = answers[idx] if idx < len(answers) else "true"
                            letter = chr(ord('a') + idx)
                            try:
                                if answer == "true":
                                    radio = tf_container.find_element(By.CSS_SELECTOR, "input[value='true']")
                                    label_text = "Đ"
                                else:
                                    radio = tf_container.find_element(By.CSS_SELECTOR, "input[value='false']")
                                    label_text = "S"
                                
                                radio_id = radio.get_attribute("id")
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", radio)
                                
                                try:
                                    label = tf_container.find_element(By.CSS_SELECTOR, f"label[for='{radio_id}']")
                                    label.click()
                                except:
                                    self.driver.execute_script("arguments[0].click();", radio)
                                
                                self.log(f"[{name}]   Câu {letter}: {label_text}")
                            except Exception:
                                self.log(f"[{name}]   ⚠️ Lỗi câu {letter}")
                else:
                    # MULTIPLE CHOICE
                    options_elems = self.driver.find_elements(By.CSS_SELECTOR, ".question-option")
                    if options_elems:
                        self.log(f"[{name}] 🔘 Trắc nghiệm ({len(options_elems)} đáp án)")
                        
                        answer_from_file = None
                        if answer_file and should_be_correct:
                            # Try to match answer content from file
                            answer_from_file = self._match_answer_content_in_options(
                                answer_file, 
                                question_count, 
                                options_elems,
                                name
                            )
                        
                        if should_be_correct and answer_from_file is not None:
                            # answer_from_file is the index to click
                            self.log(f"[{name}] 📁 Từ file: Đáp án {chr(ord('A') + answer_from_file)}")
                            answer_index = answer_from_file
                        elif should_be_correct and not answer_file:
                            result = get_gemini_response(image_data, with_explanation=True)
                            if result and isinstance(result, tuple):
                                answer_letter, explanation = result
                            else:
                                answer_letter, explanation = result, ""
                            
                            if answer_letter and answer_letter in "ABCD":
                                self.log(f"[{name}] 💡 Đáp án: {answer_letter}")
                                answer_index = ord(answer_letter) - ord('A')
                            else:
                                answer_index = None
                        else:
                            answer_letter = random.choice(["A", "B", "C", "D"][:len(options_elems)])
                            self.log(f"[{name}] 🎲 Random: {answer_letter}")
                            answer_index = ord(answer_letter) - ord('A')
                        
                        if answer_index is not None and answer_index < len(options_elems):
                            for retry in range(3):
                                try:
                                    options_elems = self.driver.find_elements(By.CSS_SELECTOR, ".question-option")
                                    if answer_index < len(options_elems):
                                        target_option = options_elems[answer_index]
                                        self.driver.execute_script("arguments[0].scrollIntoView(true);", target_option)
                                        time.sleep(0.3)
                                        try:
                                            target_option.click()
                                        except:
                                            self.driver.execute_script("arguments[0].click();", target_option)
                                        break
                                except Exception:
                                    if retry < 2:
                                        time.sleep(0.5)
                                    continue
                    else:
                        self.log(f"[{name}] ⚠️ Không tìm thấy câu hỏi")
                        time.sleep(2)
                        continue
                
                # Click submit
                self._click_submit()
                
                # Random delay
                delay = random.uniform(delay_min, delay_max)
                self.log(f"[{name}] ⏳ Chờ {delay:.1f}s...")
                time.sleep(delay)
                
            except Exception as e:
                self.log(f"[{name}] ❌ Lỗi: {str(e)[:50]}")
                time.sleep(2)
        
        # Done
        actual_score = (correct_count / max(1, question_count)) * 10 if question_count > 0 else 0
        elapsed = (time.time() - start_time) / 60
        self.log(f"[{name}] 📊 Kết quả: {correct_count} đúng / {wrong_count} sai")
        self.log(f"[{name}] 📈 Điểm ước tính: ~{actual_score:.1f}đ")
        self.log(f"[{name}] 🏁 Hoàn thành trong {elapsed:.1f} phút")
        
        # Save answers if enabled
        if save_answers and self.answer_manager and question_count > 0:
            self.log(f"[{name}] 💾 Lưu đáp án...")
            answers_dict = {i: "answer" for i in range(1, question_count + 1)}
            self.answer_manager.save_answers(self.selected_quiz_name or "Unknown", answers_dict)
        
        self.status(name, f"✅ Xong ~{actual_score:.1f}đ")
        
        # Post-completion: Submit quiz and extract real answers
        if save_answers and self.answer_manager:
            self.log(f"[{name}] 📤 Post-completion: Nộp bài và lưu đáp án thực tế...")
            self._submit_and_save_answers(name)
        
    def _submit_and_save_answers(self, name):
        """
        Post-completion flow:
        1. Finish quiz (press Kết thúc button)
        2. Wait 10 seconds
        3. Submit (press Nộp bài)
        4. Go to assignment page
        5. Find quiz in list and click
        6. View details
        7. Extract real answers from HTML
        8. Save to backend
        """
        try:
            # Step 1: Press Kết thúc button
            self.log(f"[{name}] ⏸️ Tìm nút 'Kết thúc'...")
            try:
                finish_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Kết thúc')]"))
                )
                finish_btn.click()
                self.log(f"[{name}] ✅ Ấn 'Kết thúc'")
            except:
                self.log(f"[{name}] ⚠️ Không tìm nút 'Kết thúc'")
            
            # Step 2: Wait 10 seconds
            self.log(f"[{name}] ⏳ Chờ 10 giây...")
            for i in range(10):
                time.sleep(1)
                if (i + 1) % 5 == 0:
                    self.log(f"[{name}]   {10 - i}s còn lại...")
            
            # Step 3: Submit (Nộp bài)
            self.log(f"[{name}] 📤 Tìm nút 'Nộp bài'...")
            try:
                submit_selectors = [
                    "//button[contains(text(), 'Nộp bài')]",
                    "//div[contains(text(), 'Nộp bài')]",
                    ".btn-submit",
                    ".submit-btn"
                ]
                
                submit_found = False
                for selector in submit_selectors:
                    try:
                        if selector.startswith("//"):
                            submit_btn = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                        else:
                            submit_btn = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                        
                        submit_btn.click()
                        self.log(f"[{name}] ✅ Ấn 'Nộp bài'")
                        submit_found = True
                        break
                    except:
                        continue
                
                if not submit_found:
                    self.log(f"[{name}] ⚠️ Không tìm nút 'Nộp bài'")
            except Exception as e:
                self.log(f"[{name}] ⚠️ Lỗi nộp bài: {e}")
            
            # Wait for page to process
            time.sleep(3)
            
            # Step 4: Go to assignment page
            self.log(f"[{name}] 🔗 Vào trang assignment...")
            try:
                self.driver.get("https://app.onluyen.vn/school/student/assignment?view=1&status=0")
                time.sleep(3)
            except Exception as e:
                self.log(f"[{name}] ❌ Lỗi vào trang assignment: {e}")
                return
            
            # Step 5 & 6: Find quiz and view details
            quiz_info = self._find_and_open_quiz_details(name)
            if not quiz_info:
                self.log(f"[{name}] ❌ Không tìm được bài quiz vừa làm")
                return
            
            # Step 7: Extract answers
            answers_data = self._extract_answers_from_details(name)
            if not answers_data:
                self.log(f"[{name}] ⚠️ Không lấy được đáp án từ trang chi tiết")
                return
            
            # Step 8: Save to backend
            if answers_data and answers_data.get("questions"):
                quiz_name = quiz_info.get("quiz_name", "Unknown")
                subject = quiz_info.get("subject", "")
                questions_count = len(answers_data.get("questions", []))
                self.log(f"[{name}] 📥 Lưu {questions_count} câu hỏi với đáp án cho: {subject} - {quiz_name}...")
                self.answer_manager.save_answers(f"{subject}#{quiz_name}", answers_data)
                self.log(f"[{name}] ✅ Đã lưu {questions_count} câu thành công!")
            
        except Exception as e:
            self.log(f"[{name}] ❌ Lỗi post-completion: {type(e).__name__}: {e}")
    
    def _find_and_open_quiz_details(self, name):
        """
        Find quiz in assignment list and open details page
        Returns: {"quiz_name": "...", "subject": "...", "element": ...}
        """
        try:
            # Find all assignment containers
            self.log(f"[{name}] 🔍 Tìm bài vừa làm trong danh sách...")
            
            # Look for recently completed assignments
            # The HTML structure has:
            # .content > .title (subject name)
            # .box > .class-as (assignment item)
            
            contents = self.driver.find_elements(By.CSS_SELECTOR, ".content.ng-star-inserted")
            
            for content in contents:
                try:
                    # Get subject name from .title
                    title_elem = content.find_element(By.CSS_SELECTOR, ".title")
                    subject = title_elem.text.strip()
                    
                    # Find assignments in this subject
                    assignments = content.find_elements(By.CSS_SELECTOR, ".class-as.ng-star-inserted")
                    
                    for assignment in assignments:
                        try:
                            # Get quiz name from .name
                            name_elem = assignment.find_element(By.CSS_SELECTOR, ".name-as .name")
                            quiz_name = name_elem.text.strip()
                            
                            # Check if this is the quiz we just did
                            # Look for "Đã làm xong" status (status-3)
                            status_elem = assignment.find_element(By.CSS_SELECTOR, ".status-type-assignment")
                            status_text = status_elem.text.lower()
                            
                            if "đã làm xong" in status_text or "done" in status_text:
                                self.log(f"[{name}] ✅ Tìm thấy bài: {subject} - {quiz_name}")
                                
                                # Click on this assignment to view details
                                # Look for the "Chi tiết" or eye icon button
                                try:
                                    detail_btn = assignment.find_element(
                                        By.CSS_SELECTOR, 
                                        ".btn-func[title*='Xem kết quả'], .btn-func[title*='Chi tiết']"
                                    )
                                    detail_btn.click()
                                    self.log(f"[{name}] 👁️ Ấn nút chi tiết")
                                    time.sleep(3)
                                    
                                    return {
                                        "quiz_name": quiz_name,
                                        "subject": subject,
                                        "element": assignment
                                    }
                                except:
                                    # If direct button click fails, try clicking on the name
                                    name_elem.click()
                                    self.log(f"[{name}] 👁️ Ấn vào tên bài")
                                    time.sleep(3)
                                    
                                    return {
                                        "quiz_name": quiz_name,
                                        "subject": subject,
                                        "element": assignment
                                    }
                        except:
                            continue
                except:
                    continue
            
            self.log(f"[{name}] ⚠️ Không tìm thấy bài 'Đã làm xong'")
            return None
            
        except Exception as e:
            self.log(f"[{name}] ❌ Lỗi tìm bài: {e}")
            return None
    
    def _get_answer_from_file(self, answer_file, question_num, answer_type):
        """
        Get answer from file for a specific question number and type
        Returns: answer_content (string) or None
        """
        try:
            questions = answer_file.get("questions", [])
            if question_num <= len(questions):
                q = questions[question_num - 1]
                if q.get("answer_type") == answer_type:
                    return q.get("answer_content")
            return None
        except:
            return None
    
    def _match_answer_content_in_options(self, answer_file, question_num, options_elems, name):
        """
        Match answer content from file with current options on page
        Returns: index (0-3) of matching option, or None if no match
        """
        try:
            questions = answer_file.get("questions", [])
            if question_num > len(questions):
                return None
            
            q = questions[question_num - 1]
            if q.get("answer_type") != "multiple_choice":
                return None
            
            expected_content = q.get("answer_content", "").lower()
            if not expected_content:
                return None
            
            # Try to match answer content with option text
            for idx, option in enumerate(options_elems):
                try:
                    option_text = option.text.lower()
                    
                    # Similarity check: if more than 60% of words match, consider it a match
                    if self._similarity_ratio(expected_content, option_text) > 0.6:
                        self.log(f"[{name}]   ✅ Match: Đáp án {chr(ord('A') + idx)}")
                        return idx
                    
                    # Alternative: check if key parts of answer are in option
                    if self._contains_key_parts(expected_content, option_text):
                        self.log(f"[{name}]   ✅ Match: Đáp án {chr(ord('A') + idx)}")
                        return idx
                except:
                    continue
            
            self.log(f"[{name}]   ⚠️ Không match được nội dung đáp án, dùng Gemini")
            return None
            
        except Exception as e:
            self.log(f"[{name}]   ❌ Lỗi match: {e}")
            return None
    
    def _similarity_ratio(self, str1, str2):
        """
        Calculate similarity ratio between two strings (0-1)
        """
        try:
            # Simple word-based similarity
            words1 = set(str1.split())
            words2 = set(str2.split())
            
            if not words1 or not words2:
                return 0
            
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            return intersection / union if union > 0 else 0
        except:
            return 0
    
    def _contains_key_parts(self, answer, option):
        """
        Check if option contains key parts of the answer
        """
        try:
            # Get significant words (more than 3 chars)
            key_words = [w for w in answer.split() if len(w) > 3]
            
            if not key_words:
                return False
            
            # Check if at least 50% of key words are in option
            matches = sum(1 for w in key_words if w in option)
            return matches >= len(key_words) * 0.5
        except:
            return False
    
    def _extract_answers_from_details(self, name):
        """
        Extract answers from details page HTML with question content
        Returns: {
            "questions": [
                {
                    "question": "Câu hỏi nội dung...",
                    "answer_type": "multiple_choice|true_false|short_answer",
                    "answer_content": "Nội dung đáp án hoặc giá trị",
                    "answer_letter": "A|B|C|D|true|false" (nếu có)
                },
                ...
            ]
        }
        """
        try:
            self.log(f"[{name}] 📖 Parse trang chi tiết để lấy câu hỏi và đáp án...")
            
            questions_list = []
            question_num = 0
            
            # Find all question containers
            question_containers = self.driver.find_elements(
                By.CSS_SELECTOR, 
                ".question-content.correct-answer"
            )
            
            self.log(f"[{name}] 🔢 Tìm thấy {len(question_containers)} câu")
            
            for question_container in question_containers:
                try:
                    question_num += 1
                    
                    # Extract question text
                    question_text = ""
                    try:
                        q_elem = question_container.find_element(By.CSS_SELECTOR, ".question-content")
                        question_text = q_elem.text.strip()
                        # Remove "Câu X" prefix if present
                        if question_text.startswith("Câu"):
                            question_text = question_text.split("\n", 1)[-1].strip()
                    except:
                        question_text = f"Câu {question_num}"
                    
                    # Check for multiple choice options
                    all_options = question_container.find_elements(
                        By.CSS_SELECTOR, 
                        ".question-option"
                    )
                    correct_options = question_container.find_elements(
                        By.CSS_SELECTOR, 
                        ".question-option.bg-correct"
                    )
                    
                    if all_options and correct_options:
                        # Multiple choice: get the correct answer content (text, not just A/B/C/D)
                        correct_option = correct_options[0]
                        
                        # Get letter (A, B, C, D)
                        try:
                            option_label = correct_option.find_element(
                                By.CSS_SELECTOR, 
                                ".question-option-label"
                            )
                            answer_letter = option_label.text.strip()
                        except:
                            answer_letter = "?"
                        
                        # Get full content of answer
                        try:
                            option_content = correct_option.find_element(
                                By.CSS_SELECTOR,
                                ".question-option-content"
                            )
                            answer_content = option_content.text.strip()
                            # Remove bold tags and extra whitespace
                            answer_content = answer_content.replace("<strong>", "").replace("</strong>", "").strip()
                        except:
                            answer_content = answer_letter
                        
                        self.log(f"[{name}]   Câu {question_num}: {answer_letter} (trắc nghiệm)")
                        self.log(f"[{name}]      → {answer_content[:60]}...")
                        
                        questions_list.append({
                            "question": question_text,
                            "answer_type": "multiple_choice",
                            "answer_letter": answer_letter,
                            "answer_content": answer_content
                        })
                    else:
                        # Check for true/false
                        tf_containers = question_container.find_elements(
                            By.CSS_SELECTOR,
                            ".true-false"
                        )
                        
                        if tf_containers:
                            # True/False question
                            # Find which option is marked as correct
                            tf_correct = question_container.find_elements(
                                By.CSS_SELECTOR,
                                ".true-false.bg-correct, input[type='radio'][checked]"
                            )
                            
                            answer_value = "?"
                            answer_content = "?"
                            
                            if tf_correct:
                                try:
                                    # Try to get the value from checked radio
                                    checked_radios = question_container.find_elements(
                                        By.CSS_SELECTOR,
                                        "input[type='radio'][checked]"
                                    )
                                    if checked_radios:
                                        answer_value = checked_radios[0].get_attribute("value")
                                        answer_content = "Đúng" if answer_value == "true" else "Sai"
                                except:
                                    pass
                            
                            self.log(f"[{name}]   Câu {question_num}: {answer_content} (đúng/sai)")
                            
                            questions_list.append({
                                "question": question_text,
                                "answer_type": "true_false",
                                "answer_letter": answer_value,
                                "answer_content": answer_content
                            })
                        else:
                            # Check for short answer
                            try:
                                short_answer_elems = question_container.find_elements(
                                    By.CSS_SELECTOR,
                                    ".answer-input input[type='text'], input[id^='mathplay-answer']"
                                )
                                
                                if short_answer_elems:
                                    answer_text = short_answer_elems[0].get_attribute("value") or ""
                                    self.log(f"[{name}]   Câu {question_num}: {answer_text} (tự luận)")
                                    
                                    questions_list.append({
                                        "question": question_text,
                                        "answer_type": "short_answer",
                                        "answer_letter": None,
                                        "answer_content": answer_text
                                    })
                                else:
                                    # Try to find answer in hint/explanation
                                    try:
                                        hint_elem = question_container.find_element(
                                            By.CSS_SELECTOR,
                                            ".hint-content"
                                        )
                                        answer_text = hint_elem.text.strip()
                                        self.log(f"[{name}]   Câu {question_num}: {answer_text[:50]}... (từ hint)")
                                        
                                        questions_list.append({
                                            "question": question_text,
                                            "answer_type": "short_answer",
                                            "answer_letter": None,
                                            "answer_content": answer_text
                                        })
                                    except:
                                        pass
                            except:
                                pass
                
                except Exception as q_error:
                    # Log but continue to next question
                    pass
            
            self.log(f"[{name}] ✅ Lấy được {len(questions_list)} câu hỏi với đáp án")
            
            return {
                "questions": questions_list
            } if questions_list else None
            
        except Exception as e:
            self.log(f"[{name}] ❌ Lỗi parse đáp án: {e}")
            import traceback
            self.log(f"[{name}] {traceback.format_exc()}")
            return None
        
    def _click_submit(self):
        """Click submit button with multiple selectors"""
        selectors = [
            "//div[contains(@class, 'btn')]//span[contains(text(), 'Trả lời')]/parent::div",
            "//div[contains(., 'Trả lời') and contains(@class, 'btn')]",
            ".btn-primary",
        ]
        
        for selector in selectors:
            try:
                if selector.startswith("//"):
                    btn = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    btn = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                
                if "Nộp bài" in btn.text:
                    continue
                
                btn.click()
                return True
            except:
                continue
        return False
    
    def _fake_mouse_activity(self):
        """Simulate mouse movement inside browser"""
        try:
            window_size = self.driver.get_window_size()
            width = window_size['width']
            height = window_size['height']
            
            x = random.randint(100, max(200, width - 200))
            y = random.randint(100, max(200, height - 200))
            
            self.driver.execute_script(f"""
                var event = new MouseEvent('mousemove', {{
                    'view': window,
                    'bubbles': true,
                    'cancelable': true,
                    'clientX': {x},
                    'clientY': {y}
                }});
                document.dispatchEvent(event);
            """)
            
            if random.random() < 0.3:
                scroll_amount = random.randint(-50, 50)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        except:
            pass


class MultiAccountApp:
    """Main UI for multi-account management"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Quiz Solver - Multi Account")
        self.root.geometry("1000x700")
        self.root.configure(bg="#1a1a2e")
        
        self.accounts = []
        self.workers = {}
        self.config = self.load_config()
        
        self.setup_styles()
        self.create_widgets()
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Card.TFrame", background="#16213e")
        style.configure("Dark.TFrame", background="#1a1a2e")
        style.configure("Title.TLabel", background="#1a1a2e", foreground="#e94560", font=("Segoe UI", 16, "bold"))
        style.configure("Subtitle.TLabel", background="#16213e", foreground="#eaeaea", font=("Segoe UI", 11, "bold"))
        style.configure("Normal.TLabel", background="#16213e", foreground="#eaeaea", font=("Segoe UI", 10))
        
    def create_widgets(self):
        main = ttk.Frame(self.root, style="Dark.TFrame")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        ttk.Label(main, text="🎯 Quiz Solver - Multi Account Advanced", style="Title.TLabel").pack(pady=(0, 15))
        
        # Settings Panel
        settings_frame = ttk.Frame(main, style="Card.TFrame")
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(settings_frame, text="⚙️ Cài Đặt Chung", style="Subtitle.TLabel").pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        # Settings grid
        settings_inner = ttk.Frame(settings_frame, style="Card.TFrame")
        settings_inner.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        # Row 1
        row1 = ttk.Frame(settings_inner, style="Card.TFrame")
        row1.pack(fill=tk.X, pady=3)
        
        ttk.Label(row1, text="Backend URL:", style="Normal.TLabel", width=15).pack(side=tk.LEFT)
        self.backend_url_var = tk.StringVar(value=self.config.get("backend_url", "http://localhost:8000"))
        ttk.Entry(row1, textvariable=self.backend_url_var, width=30).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(row1, text="Delay (min-max):", style="Normal.TLabel", width=15).pack(side=tk.LEFT)
        self.delay_min_var = tk.StringVar(value=self.config.get("delay_min", "3"))
        self.delay_max_var = tk.StringVar(value=self.config.get("delay_max", "8"))
        ttk.Entry(row1, textvariable=self.delay_min_var, width=5).pack(side=tk.LEFT)
        ttk.Label(row1, text=" - ", style="Normal.TLabel").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.delay_max_var, width=5).pack(side=tk.LEFT)
        ttk.Label(row1, text="s", style="Normal.TLabel").pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(row1, text="Thời gian:", style="Normal.TLabel", width=10).pack(side=tk.LEFT)
        self.quiz_time_var = tk.StringVar(value=self.config.get("quiz_time", "30"))
        ttk.Entry(row1, textvariable=self.quiz_time_var, width=5).pack(side=tk.LEFT)
        ttk.Label(row1, text="p", style="Normal.TLabel").pack(side=tk.LEFT)
        
        # Row 2
        row2 = ttk.Frame(settings_inner, style="Card.TFrame")
        row2.pack(fill=tk.X, pady=3)
        
        ttk.Label(row2, text="Tổng câu:", style="Normal.TLabel", width=15).pack(side=tk.LEFT)
        self.total_q_var = tk.StringVar(value=self.config.get("total_questions", "40"))
        ttk.Entry(row2, textvariable=self.total_q_var, width=5).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(row2, text="Điểm cần:", style="Normal.TLabel", width=15).pack(side=tk.LEFT)
        self.target_var = tk.StringVar(value=self.config.get("target_score", "7.0"))
        ttk.Entry(row2, textvariable=self.target_var, width=5).pack(side=tk.LEFT, padx=(0, 20))
        
        # Checkboxes
        check_frame = ttk.Frame(row2, style="Card.TFrame")
        check_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 20))
        
        self.check_answers_var = tk.BooleanVar(value=self.config.get("check_answer_files", True))
        ttk.Checkbutton(check_frame, text="📁 Kiểm tra file đáp án", variable=self.check_answers_var).pack(side=tk.LEFT, padx=5)
        
        self.save_answers_var = tk.BooleanVar(value=self.config.get("save_answer_files", False))
        ttk.Checkbutton(check_frame, text="💾 Lưu đáp án", variable=self.save_answers_var).pack(side=tk.LEFT, padx=5)
        
        self.auto_detect_var = tk.BooleanVar(value=self.config.get("auto_detect", False))
        ttk.Checkbutton(check_frame, text="🔍 Auto-detect bài", variable=self.auto_detect_var).pack(side=tk.LEFT, padx=5)
        
        # Account panel
        top = ttk.Frame(main, style="Dark.TFrame")
        top.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        acc_frame = ttk.Frame(top, style="Card.TFrame")
        acc_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(acc_frame, text="👥 Danh Sách Tài Khoản", style="Subtitle.TLabel").pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        # Account table
        columns = ("name", "username", "api_key", "proxy_key", "status")
        self.tree = ttk.Treeview(acc_frame, columns=columns, show="headings", height=8)
        self.tree.heading("name", text="Tên")
        self.tree.heading("username", text="Tài khoản")
        self.tree.heading("api_key", text="API Key")
        self.tree.heading("proxy_key", text="Proxy Key")
        self.tree.heading("status", text="Trạng thái")
        
        self.tree.column("name", width=100)
        self.tree.column("username", width=120)
        self.tree.column("api_key", width=150)
        self.tree.column("proxy_key", width=150)
        self.tree.column("status", width=100)
        
        self.tree.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))
        
        # Load accounts
        for acc in self.config.get("accounts", []):
            self.tree.insert("", tk.END, values=(
                acc.get("name", ""),
                acc.get("username", ""),
                acc.get("api_key", "")[:20] + "..." if acc.get("api_key") else "",
                acc.get("proxy_key", "")[:20] + "..." if acc.get("proxy_key") else "",
                "⚪ Chờ"
            ))
            self.accounts.append(acc)
        
        # Account buttons
        btn_frame = ttk.Frame(acc_frame, style="Card.TFrame")
        btn_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        tk.Button(btn_frame, text="➕ Thêm", bg="#22c55e", fg="white", command=self.add_account).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="✏️ Sửa", bg="#3b82f6", fg="white", command=self.edit_account).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="🗑️ Xóa", bg="#ef4444", fg="white", command=self.delete_account).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="🔍 Tìm Bài", bg="#f59e0b", fg="white", command=self.detect_all_assignments).pack(side=tk.LEFT, padx=2)
        
        # Controls
        ctrl_frame = ttk.Frame(main, style="Card.TFrame")
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Button(ctrl_frame, text="🌐 Mở Chrome", bg="#3b82f6", fg="white", font=("Segoe UI", 11, "bold"),
                 command=self.open_all_browsers, padx=20, pady=5).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(ctrl_frame, text="▶ Bắt Đầu Giải", bg="#22c55e", fg="white", font=("Segoe UI", 11, "bold"),
                 command=self.start_all_solving, padx=20, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl_frame, text="⏹ Dừng Tất Cả", bg="#ef4444", fg="white", font=("Segoe UI", 11, "bold"),
                 command=self.stop_all, padx=20, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl_frame, text="💾 Lưu Cấu Hình", bg="#6b7280", fg="white",
                 command=self.save_config, padx=10).pack(side=tk.RIGHT, padx=10, pady=10)
        
        # Log
        log_frame = ttk.Frame(main, style="Card.TFrame")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(log_frame, text="📋 Nhật Ký", style="Subtitle.TLabel").pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, bg="#0d1117", fg="#58a6ff", font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.update()
        
    def update_status(self, name, status):
        for item in self.tree.get_children():
            values = list(self.tree.item(item)["values"])
            if values[0] == name:
                values[4] = status
                self.tree.item(item, values=values)
                break
    
    def detect_all_assignments(self):
        """Detect assignments for all accounts"""
        if not self.workers:
            messagebox.showinfo("Thông báo", "Chưa mở Chrome! Bấm 'Mở Chrome' trước.")
            return
        
        self.log("🔍 Tìm bài chưa làm cho tất cả...")
        for name, worker in self.workers.items():
            worker.detect_assignments()
            time.sleep(1)
                
    def add_account(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Thêm Tài Khoản")
        dialog.geometry("500x400")
        dialog.configure(bg="#1a1a2e")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Tên:", background="#1a1a2e", foreground="white").pack(pady=5)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=50).pack()
        
        ttk.Label(dialog, text="Tài khoản:", background="#1a1a2e", foreground="white").pack(pady=5)
        user_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=user_var, width=50).pack()
        
        ttk.Label(dialog, text="Mật khẩu:", background="#1a1a2e", foreground="white").pack(pady=5)
        pass_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=pass_var, width=50, show="*").pack()
        
        ttk.Label(dialog, text="Gemini API Key:", background="#1a1a2e", foreground="white").pack(pady=5)
        api_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=api_var, width=50, show="*").pack()
        
        ttk.Label(dialog, text="Proxy Key (proxyxoay.shop):", background="#1a1a2e", foreground="white").pack(pady=5)
        proxy_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=proxy_var, width=50, show="*").pack()
        
        def save():
            acc = {
                "name": name_var.get(),
                "username": user_var.get(),
                "password": pass_var.get(),
                "api_key": api_var.get(),
                "proxy_key": proxy_var.get()
            }
            self.accounts.append(acc)
            api_display = acc["api_key"][:20] + "..." if acc["api_key"] else ""
            proxy_display = acc["proxy_key"][:20] + "..." if acc["proxy_key"] else ""
            self.tree.insert("", tk.END, values=(acc["name"], acc["username"], api_display, proxy_display, "⚪ Chờ"))
            dialog.destroy()
            
        tk.Button(dialog, text="Lưu", bg="#22c55e", fg="white", command=save).pack(pady=15)
        
    def edit_account(self):
        selected = self.tree.selection()
        if not selected:
            return
        # TODO: Implement edit
        
    def delete_account(self):
        selected = self.tree.selection()
        if not selected:
            return
        idx = self.tree.index(selected[0])
        self.tree.delete(selected[0])
        if idx < len(self.accounts):
            del self.accounts[idx]
            
    def open_all_browsers(self):
        """Open Chrome for all accounts"""
        if not self.accounts:
            messagebox.showerror("Lỗi", "Chưa có tài khoản nào!")
            return
            
        settings = {
            "backend_url": self.backend_url_var.get(),
            "delay_min": self.delay_min_var.get(),
            "delay_max": self.delay_max_var.get(),
            "quiz_time": self.quiz_time_var.get(),
            "total_questions": self.total_q_var.get(),
            "target_score": self.target_var.get(),
            "check_answer_files": self.check_answers_var.get(),
            "save_answer_files": self.save_answers_var.get(),
            "auto_detect": self.auto_detect_var.get()
        }
        
        self.log("🌐 Đang mở Chrome cho tất cả tài khoản (lần lượt, 60s giữa các tài khoản)...")
        
        for idx, acc in enumerate(self.accounts):
            name = acc.get('name', 'Unknown')
            self.log(f"[{idx+1}/{len(self.accounts)}] Mở Chrome cho: {name}")
            
            worker = AccountWorker(acc, self.log, self.update_status, settings)
            self.workers[name] = worker
            
            # Open browser synchronously (waits until it's ready or timeout)
            worker.open_browser_sync()
            
            if worker.browser_ready:
                self.log(f"✅ Chrome cho {name} đã sẵn sàng")
            else:
                self.log(f"⚠️ Chrome cho {name} chưa sẵn sàng")
            
            # Wait 60 seconds before opening next Chrome
            if idx < len(self.accounts) - 1:
                self.log(f"⏳ Đợi 60s trước khi mở Chrome tiếp theo...")
                for i in range(60):
                    time.sleep(1)
                    if i % 10 == 0:
                        self.log(f"   Còn {60-i}s")
            
    def start_all_solving(self):
        """Start solving for all accounts"""
        if not self.workers:
            messagebox.showerror("Lỗi", "Chưa mở Chrome! Bấm 'Mở Chrome' trước.")
            return
            
        self.log("🚀 Bắt đầu giải bài cho tất cả...")
        
        for name, worker in self.workers.items():
            worker.start_solving()
            time.sleep(1)
            
    def stop_all(self):
        self.log("⏹ Dừng tất cả...")
        for name, worker in self.workers.items():
            worker.stop()
            self.update_status(name, "⏹ Dừng")
            
    def load_config(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
        
    def save_config(self):
        config = {
            "backend_url": self.backend_url_var.get(),
            "delay_min": self.delay_min_var.get(),
            "delay_max": self.delay_max_var.get(),
            "quiz_time": self.quiz_time_var.get(),
            "total_questions": self.total_q_var.get(),
            "target_score": self.target_var.get(),
            "check_answer_files": self.check_answers_var.get(),
            "save_answer_files": self.save_answers_var.get(),
            "auto_detect": self.auto_detect_var.get(),
            "accounts": self.accounts
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        self.log("✅ Đã lưu cấu hình!")
        messagebox.showinfo("Thành công", "Đã lưu cấu hình!")


if __name__ == "__main__":
    root = tk.Tk()
    app = MultiAccountApp(root)
    root.mainloop()
