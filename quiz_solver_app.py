"""
Quiz Solver UI - Modern GUI with Auto Login
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import json
import os
import time
import io
import random
from datetime import datetime
from datetime import datetime
from pathlib import Path
import license_utils  # Import license utilities

# Import quiz solver functions
import google.generativeai as genai
from PIL import Image
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
import undetected_chromedriver as uc
import sys

# Config file path - works for both .py and .exe
def get_app_path():
    """Get the directory where the app/exe is located"""
    if getattr(sys, 'frozen', False):
        # Running as compiled .exe
        return Path(sys.executable).parent
    else:
        # Running as .py script
        return Path(__file__).parent

APP_DIR = get_app_path()
CONFIG_FILE = APP_DIR / "config.json"

class QuizSolverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quiz Solver - Ôn Luyện VN")
        self.root.geometry("900x900")  # Larger default size
        self.root.minsize(700, 600)    # Minimum size
        self.root.configure(bg="#1a1a2e")
        
        # State
        self.driver = None
        self.is_running = False
        self.stop_flag = False
        self.automation_thread = None
        self.detected_assignments = []
        self.selected_assignment_name = ""
        
        # Load config
        self.config = self.load_config()
        
        # Setup UI
        self.setup_styles()
        self.create_widgets()
        
        # Check License (after UI is ready)
        
        # Check for updates
        self.root.after(500, self.check_for_updates)

    # Tool version
    TOOL_VERSION = "1.1.0"
    
    def check_for_updates(self):
        """Check if there's a new version available and auto-update"""
        import requests
        import webbrowser
        import zipfile
        import shutil
        import subprocess
        import sys
        
        try:
            server_url = license_utils.SERVER_URL
            resp = requests.post(
                f"{server_url}/check_update", 
                json={"version": self.TOOL_VERSION},
                timeout=5
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("needs_update"):
                    new_version = data.get("current_version", "?")
                    changelog = data.get("changelog", "")
                    download_url = data.get("download_url", "")
                    force = data.get("force_update", False)
                    auto_update = data.get("auto_update", True)  # New field
                    
                    if force:
                        messagebox.showwarning("Cập Nhật Bắt Buộc", 
                            f"Phiên bản này đã lỗi thời!\n\nVui lòng cập nhật lên v{new_version} để tiếp tục sử dụng.")
                        if download_url:
                            self.auto_update(download_url, new_version)
                        else:
                            self.root.destroy()
                        return
                    
                    msg = f"Có phiên bản mới: v{new_version}\n\n"
                    if changelog:
                        msg += f"Thay đổi: {changelog}\n\n"
                    
                    if auto_update and download_url:
                        msg += "Tool sẽ tự động cập nhật. Tiếp tục?"
                        if messagebox.askyesno("Cập Nhật Tự Động", msg):
                            self.auto_update(download_url, new_version)
                        else:
                            self.log(f"ℹ️ Đang dùng v{self.TOOL_VERSION}, mới nhất là v{new_version}")
                    else:
                        msg += "Bạn có muốn mở link tải về không?"
                        if messagebox.askyesno("Cập Nhật Mới", msg):
                            if download_url:
                                webbrowser.open(download_url)
                        else:
                            self.log(f"ℹ️ Đang dùng v{self.TOOL_VERSION}, mới nhất là v{new_version}")
                else:
                    self.log(f"✅ Đang dùng phiên bản mới nhất: v{self.TOOL_VERSION}")
        except Exception as e:
            print(f"Update check failed: {e}")
    
    def auto_update(self, download_url, new_version):
        """Auto download and update the tool"""
        import requests
        import zipfile
        import shutil
        import subprocess
        import sys
        import os
        import tempfile
        
        try:
            self.log(f"🔄 Đang tải bản cập nhật v{new_version}...")
            self.status_var.set("🔄 Đang cập nhật...")
            self.root.update()
            
            # Download the update
            resp = requests.get(download_url, stream=True, timeout=60)
            if resp.status_code != 200:
                messagebox.showerror("Lỗi", "Không thể tải bản cập nhật!")
                return
            
            # Save to temp file
            temp_dir = tempfile.gettempdir()
            update_file = os.path.join(temp_dir, "quiz_solver_update.zip")
            
            with open(update_file, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.log("📦 Đang giải nén...")
            
            # Extract update
            current_dir = APP_DIR
            backup_dir = current_dir / "backup"
            extract_dir = os.path.join(temp_dir, "quiz_solver_extracted")
            
            # Clean old extract
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            
            with zipfile.ZipFile(update_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find files to update (py files)
            update_files = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file.endswith('.py'):
                        update_files.append((os.path.join(root, file), file))
            
            if not update_files:
                # Try one level deeper (if zip contains folder)
                for subdir in os.listdir(extract_dir):
                    subpath = os.path.join(extract_dir, subdir)
                    if os.path.isdir(subpath):
                        for file in os.listdir(subpath):
                            if file.endswith('.py'):
                                update_files.append((os.path.join(subpath, file), file))
            
            if update_files:
                self.log(f"📝 Cập nhật {len(update_files)} file...")
                
                # Backup current files
                backup_dir.mkdir(exist_ok=True)
                for src, filename in update_files:
                    dst = current_dir / filename
                    if dst.exists():
                        shutil.copy(dst, backup_dir / filename)
                    shutil.copy(src, dst)
                
                self.log("✅ Cập nhật thành công!")
                messagebox.showinfo("Hoàn Tất", 
                    f"Đã cập nhật lên v{new_version}!\n\nTool sẽ khởi động lại.")
                
                # Restart the tool
                python = sys.executable
                os.execl(python, python, *sys.argv)
            else:
                messagebox.showerror("Lỗi", "Không tìm thấy file cập nhật trong gói tải về!")
                
        except Exception as e:
            self.log(f"❌ Lỗi cập nhật: {e}")
            messagebox.showerror("Lỗi Cập Nhật", f"Không thể cập nhật: {e}")

    
    def setup_styles(self):
        """Setup custom styles for modern look"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Colors
        self.bg_dark = "#1a1a2e"
        self.bg_card = "#16213e"
        self.accent = "#0f3460"
        self.accent_light = "#e94560"
        self.text_color = "#eaeaea"
        self.text_muted = "#a0a0a0"
        
        # Configure styles
        style.configure("Card.TFrame", background=self.bg_card)
        style.configure("Dark.TFrame", background=self.bg_dark)
        style.configure("Title.TLabel", 
                       background=self.bg_dark, 
                       foreground=self.accent_light,
                       font=("Segoe UI", 16, "bold"))
        style.configure("Subtitle.TLabel",
                       background=self.bg_card,
                       foreground=self.text_color,
                       font=("Segoe UI", 10, "bold"))
        style.configure("Normal.TLabel",
                       background=self.bg_card,
                       foreground=self.text_color,
                       font=("Segoe UI", 10))
        style.configure("Accent.TButton",
                       background=self.accent_light,
                       foreground="white",
                       font=("Segoe UI", 10, "bold"),
                       padding=(20, 10))
        style.configure("Secondary.TButton",
                       background=self.accent,
                       foreground="white",
                       font=("Segoe UI", 10),
                       padding=(15, 8))
        style.configure("Status.TLabel",
                       background=self.bg_card,
                       foreground="#4ade80",
                       font=("Segoe UI", 10, "bold"))
                       
    def create_widgets(self):
        """Create all UI widgets"""
        # Main container with scrollbar
        main_frame = ttk.Frame(self.root, style="Dark.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Title
        title = ttk.Label(main_frame, text="🎯 Quiz Solver - Ôn Luyện VN", 
                         style="Title.TLabel", font=("Segoe UI", 18, "bold"))
        title.pack(anchor=tk.W, pady=(0, 20))
        
        # Control Section (Top - most important)
        self.create_control_section(main_frame)
        
        # Login Section
        self.create_login_section(main_frame)
        
        # API Key Section
        self.create_api_section(main_frame)
        
        # Features Section
        self.create_features_section(main_frame)
        
        # Detected Assignments Section
        self.create_assignments_section(main_frame)
        
        # Log Section (Bottom - takes remaining space)
        self.create_log_section(main_frame)
        
    def create_login_section(self, parent):
        """Create login form section"""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill=tk.X, pady=(0, 12))
        
        # Header
        header = ttk.Label(frame, text="🔐 Đăng Nhập", style="Subtitle.TLabel")
        header.pack(anchor=tk.W, padx=12, pady=(12, 8))
        
        # Content frame
        content = ttk.Frame(frame, style="Card.TFrame")
        content.pack(fill=tk.X, padx=12, pady=(0, 12))
        
        # Row 1: Username + Password
        row1 = ttk.Frame(content, style="Card.TFrame")
        row1.pack(fill=tk.X, pady=4)
        
        ttk.Label(row1, text="Tài khoản:", style="Normal.TLabel", width=10).pack(side=tk.LEFT)
        self.username_var = tk.StringVar(value=self.config.get("username", ""))
        self.username_entry = ttk.Entry(row1, textvariable=self.username_var, width=25)
        self.username_entry.pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(row1, text="Mật khẩu:", style="Normal.TLabel", width=10).pack(side=tk.LEFT)
        self.password_var = tk.StringVar(value=self.config.get("password", ""))
        self.password_entry = ttk.Entry(row1, textvariable=self.password_var, width=25, show="*")
        self.password_entry.pack(side=tk.LEFT, padx=5)
        
        # Row 2: Remember checkbox + Login buttons
        row2 = ttk.Frame(content, style="Card.TFrame")
        row2.pack(fill=tk.X, pady=8)
        
        self.remember_var = tk.BooleanVar(value=self.config.get("remember", False))
        remember_cb = ttk.Checkbutton(row2, text="Ghi nhớ", variable=self.remember_var)
        remember_cb.pack(side=tk.LEFT)
        
        # Google login button
        google_btn = tk.Button(row2, text="🔵 Google", 
                              bg="#4285f4", fg="white",
                              font=("Segoe UI", 9, "bold"),
                              relief=tk.FLAT, padx=12, pady=4,
                              command=self.google_login)
        google_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Regular login button
        login_btn = tk.Button(row2, text="🚀 Đăng Nhập", 
                             bg=self.accent_light, fg="white",
                             font=("Segoe UI", 9, "bold"),
                             relief=tk.FLAT, padx=15, pady=4,
                             command=self.auto_login)
        login_btn.pack(side=tk.RIGHT)
        
    def create_api_section(self, parent):
        """Create API key and timing settings section"""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill=tk.X, pady=(0, 12))
        
        header = ttk.Label(frame, text="⚙️ Cài Đặt", style="Subtitle.TLabel")
        header.pack(anchor=tk.W, padx=12, pady=(12, 8))
        
        # Content frame
        content = ttk.Frame(frame, style="Card.TFrame")
        content.pack(fill=tk.X, padx=12, pady=(0, 12))
        
        # Row 1: API Key
        row1 = ttk.Frame(content, style="Card.TFrame")
        row1.pack(fill=tk.X, pady=4)
        
        ttk.Label(row1, text="Gemini API:", style="Normal.TLabel", width=12).pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(value=self.config.get("api_key", ""))
        self.api_entry = ttk.Entry(row1, textvariable=self.api_key_var, width=35, show="*")
        self.api_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        save_btn = tk.Button(row1, text="💾 Lưu", 
                            bg=self.accent, fg="white",
                            font=("Segoe UI", 8),
                            relief=tk.FLAT, padx=10, pady=2,
                            command=self.save_config)
        save_btn.pack(side=tk.LEFT)
        
        # Row 2: Delay settings
        row2 = ttk.Frame(content, style="Card.TFrame")
        row2.pack(fill=tk.X, pady=4)
        
        ttk.Label(row2, text="Delay/câu:", style="Normal.TLabel", width=12).pack(side=tk.LEFT)
        self.delay_min_var = tk.StringVar(value=self.config.get("delay_min", "3"))
        self.delay_max_var = tk.StringVar(value=self.config.get("delay_max", "8"))
        
        ttk.Entry(row2, textvariable=self.delay_min_var, width=4).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(row2, text="-", style="Normal.TLabel").pack(side=tk.LEFT, padx=(2, 2))
        ttk.Entry(row2, textvariable=self.delay_max_var, width=4).pack(side=tk.LEFT)
        ttk.Label(row2, text="giây", style="Normal.TLabel").pack(side=tk.LEFT, padx=(5, 0))
        
        ttk.Label(row2, text="Làm bài:", style="Normal.TLabel", width=8).pack(side=tk.LEFT, padx=(30, 0))
        self.quiz_time_var = tk.StringVar(value=self.config.get("quiz_time", "30"))
        ttk.Entry(row2, textvariable=self.quiz_time_var, width=4).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(row2, text="phút", style="Normal.TLabel").pack(side=tk.LEFT, padx=2)
        
        # Row 3: Score settings
        row3 = ttk.Frame(content, style="Card.TFrame")
        row3.pack(fill=tk.X, pady=4)
        
        ttk.Label(row3, text="Tổng câu:", style="Normal.TLabel", width=12).pack(side=tk.LEFT)
        self.total_questions_var = tk.StringVar(value=self.config.get("total_questions", "40"))
        ttk.Entry(row3, textvariable=self.total_questions_var, width=4).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(row3, text="câu", style="Normal.TLabel").pack(side=tk.LEFT, padx=(5, 0))
        
        ttk.Label(row3, text="Điểm:", style="Normal.TLabel", width=8).pack(side=tk.LEFT, padx=(30, 0))
        self.target_score_var = tk.StringVar(value=self.config.get("target_score", "7.0"))
        ttk.Entry(row3, textvariable=self.target_score_var, width=4).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(row3, text="/10", style="Normal.TLabel").pack(side=tk.LEFT, padx=2)
        
        # Row 4: Backend URL
        row4 = ttk.Frame(content, style="Card.TFrame")
        row4.pack(fill=tk.X, pady=4)
        
        ttk.Label(row4, text="Backend:", style="Normal.TLabel", width=12).pack(side=tk.LEFT)
        self.backend_url_var = tk.StringVar(value=self.config.get("backend_url", "http://localhost:8000"))
        ttk.Entry(row4, textvariable=self.backend_url_var, width=35).pack(side=tk.LEFT, padx=5)
        
    def create_features_section(self, parent):
        """Create features/options section"""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill=tk.X, pady=(0, 12))
        
        header = ttk.Label(frame, text="🎯 Tính Năng", style="Subtitle.TLabel")
        header.pack(anchor=tk.W, padx=12, pady=(12, 8))
        
        # Content frame
        content = ttk.Frame(frame, style="Card.TFrame")
        content.pack(fill=tk.X, padx=12, pady=(0, 12))
        
        # Row 1: Auto detect + Check files
        row1 = ttk.Frame(content, style="Card.TFrame")
        row1.pack(fill=tk.X, pady=3)
        
        self.auto_detect_var = tk.BooleanVar(value=self.config.get("auto_detect", True))
        detect_cb = ttk.Checkbutton(row1, text="🔍 Tự tìm bài chưa làm", variable=self.auto_detect_var)
        detect_cb.pack(side=tk.LEFT, padx=5)
        
        self.check_answer_files_var = tk.BooleanVar(value=self.config.get("check_answer_files", True))
        check_files_cb = ttk.Checkbutton(row1, text="📁 Kiểm tra backend có đáp án", variable=self.check_answer_files_var)
        check_files_cb.pack(side=tk.LEFT, padx=(20, 5))
        
        # Row 2: Save answers + Use profile
        row2 = ttk.Frame(content, style="Card.TFrame")
        row2.pack(fill=tk.X, pady=3)
        
        self.save_answer_files_var = tk.BooleanVar(value=self.config.get("save_answer_files", False))
        save_ans_cb = ttk.Checkbutton(row2, text="💾 Lưu đáp án mới", variable=self.save_answer_files_var)
        save_ans_cb.pack(side=tk.LEFT, padx=5)
        
        self.use_profile_var = tk.BooleanVar(value=self.config.get("use_profile", True))
        profile_cb = ttk.Checkbutton(row2, text="🔵 Dùng Chrome Profile", variable=self.use_profile_var)
        profile_cb.pack(side=tk.LEFT, padx=(20, 5))
        
        # Row 3: Continue on timeout + Save answers
        row3 = ttk.Frame(content, style="Card.TFrame")
        row3.pack(fill=tk.X, pady=3)
        
        self.continue_on_timeout_var = tk.BooleanVar(value=self.config.get("continue_on_timeout", True))
        continue_cb = ttk.Checkbutton(row3, text="⏰ Timeout: Kết thúc", variable=self.continue_on_timeout_var)
        continue_cb.pack(side=tk.LEFT, padx=5)
        
        self.save_answers_var = tk.BooleanVar(value=self.config.get("save_answers", True))
        save_cb = ttk.Checkbutton(row3, text="📝 Lưu câu hỏi & đáp án", variable=self.save_answers_var)
        save_cb.pack(side=tk.LEFT, padx=(20, 5))
        
    def create_assignments_section(self, parent):
        """Create section to display detected incomplete assignments"""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill=tk.X, pady=(0, 12))
        
        header_frame = ttk.Frame(frame, style="Card.TFrame")
        header_frame.pack(fill=tk.X, padx=12, pady=(12, 8))
        
        ttk.Label(header_frame, text="📚 Bài Chưa Làm", style="Subtitle.TLabel").pack(side=tk.LEFT)
        
        detect_btn = tk.Button(header_frame, text="🔍 Tìm Bài",
                              bg=self.accent_light, fg="white",
                              font=("Segoe UI", 8, "bold"),
                              relief=tk.FLAT, padx=10, pady=2,
                              command=self.detect_assignments)
        detect_btn.pack(side=tk.RIGHT)
        
        # Listbox to show assignments
        list_frame = ttk.Frame(frame, style="Card.TFrame")
        list_frame.pack(fill=tk.X, padx=12, pady=(0, 8))
        
        # Scrollbar for listbox
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.assignments_listbox = tk.Listbox(
            list_frame,
            height=5,
            bg="#0d1117",
            fg="#58a6ff",
            selectmode=tk.SINGLE,
            font=("Segoe UI", 9),
            yscrollcommand=scrollbar.set,
            highlightthickness=0,
            relief=tk.FLAT
        )
        self.assignments_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.assignments_listbox.yview)
        
        # Bind double-click
        self.assignments_listbox.bind("<Double-Button-1>", self.on_assignment_selected)
        
        # Info label
        self.assignment_info_var = tk.StringVar(value="💡 Double-click để chọn hoặc bấm 'Tìm Bài'")
        info_label = ttk.Label(frame, textvariable=self.assignment_info_var, style="Normal.TLabel", foreground="#10b981")
        info_label.pack(fill=tk.X, padx=12, pady=(0, 8))
        
    def create_control_section(self, parent):
        """Create start/stop controls"""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill=tk.X, pady=(0, 12))
        
        header = ttk.Label(frame, text="🎮 Điều Khiển", style="Subtitle.TLabel")
        header.pack(anchor=tk.W, padx=12, pady=(12, 8))
        
        ctrl_frame = ttk.Frame(frame, style="Card.TFrame")
        ctrl_frame.pack(fill=tk.X, padx=12, pady=(0, 12))
        
        # Status label
        ttk.Label(ctrl_frame, text="Trạng thái:", style="Normal.TLabel", width=10).pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="⚪ Chờ đăng nhập")
        self.status_label = ttk.Label(ctrl_frame, textvariable=self.status_var, 
                                     style="Status.TLabel", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Buttons
        self.stop_btn = tk.Button(ctrl_frame, text="⏹ Dừng",
                                 bg="#ef4444", fg="white",
                                 font=("Segoe UI", 9, "bold"),
                                 relief=tk.FLAT, padx=15, pady=5,
                                 command=self.stop_automation,
                                 state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT, padx=(8, 0))
        
        self.start_btn = tk.Button(ctrl_frame, text="▶ Bắt Đầu Giải",
                                  bg="#22c55e", fg="white",
                                  font=("Segoe UI", 9, "bold"),
                                  relief=tk.FLAT, padx=15, pady=5,
                                  command=self.start_automation)
        self.start_btn.pack(side=tk.RIGHT)
        
    def create_log_section(self, parent):
        """Create log output section"""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
        
        header_frame = ttk.Frame(frame, style="Card.TFrame")
        header_frame.pack(fill=tk.X, padx=12, pady=(12, 8))
        
        ttk.Label(header_frame, text="📋 Nhật Ký", style="Subtitle.TLabel").pack(side=tk.LEFT)
        
        clear_btn = tk.Button(header_frame, text="🗑 Xóa",
                             bg=self.accent, fg="white",
                             font=("Segoe UI", 8),
                             relief=tk.FLAT, padx=10, pady=2,
                             command=self.clear_log)
        clear_btn.pack(side=tk.RIGHT)
        
        # Log text area
        self.log_text = scrolledtext.ScrolledText(frame, 
                                                  height=12,
                                                  bg="#0d1117",
                                                  fg="#58a6ff",
                                                  font=("Consolas", 9),
                                                  insertbackground="white",
                                                  relief=tk.FLAT)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        
    def log(self, message):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clear_log(self):
        """Clear log area"""
        self.log_text.delete(1.0, tk.END)
        
    def detect_assignments(self):
        """Find incomplete assignments on homepage"""
        if not self.driver:
            messagebox.showinfo("Thông báo", "Vui lòng đăng nhập trước!")
            return
        
        self.log("🔍 Tìm bài chưa làm...")
        
        # Run detection in thread
        threading.Thread(target=self._do_detect_assignments, daemon=True).start()
    
    def _do_detect_assignments(self):
        """Detect assignments in background thread"""
        try:
            from quiz_logic_advanced import AssignmentDetector
            
            detector = AssignmentDetector(self.driver)
            assignments = detector.get_incomplete_assignments()
            
            # Clear listbox
            self.assignments_listbox.delete(0, tk.END)
            self.detected_assignments = assignments
            
            if assignments:
                # Add to listbox
                for i, assignment in enumerate(assignments):
                    self.assignments_listbox.insert(tk.END, assignment.get("name", f"Bài {i+1}"))
                
                self.assignment_info_var.set(f"✅ Tìm thấy {len(assignments)} bài chưa làm - Double-click để chọn")
                self.log(f"✅ Tìm thấy {len(assignments)} bài chưa làm")
            else:
                self.assignment_info_var.set("⚠️ Không tìm thấy bài chưa làm")
                self.log("⚠️ Không tìm thấy bài chưa làm")
        
        except Exception as e:
            self.log(f"❌ Lỗi tìm bài: {e}")
            messagebox.showerror("Lỗi", f"Lỗi tìm bài: {e}")
    
    def on_assignment_selected(self, event):
        """Handle assignment selection"""
        selection = self.assignments_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        if not hasattr(self, 'detected_assignments') or idx >= len(self.detected_assignments):
            return
        
        assignment = self.detected_assignments[idx]
        
        # Click on selected assignment
        self.log(f"⏳ Mở bài: {assignment.get('name', 'Unknown')}")
        
        try:
            if "element" in assignment:
                # If we have element, click it
                self.driver.execute_script("arguments[0].click();", assignment["element"])
            elif "url" in assignment:
                # If we have URL, navigate to it
                self.driver.get(assignment["url"])
            
            time.sleep(3)
            
            # Save selected assignment name for later use
            self.selected_assignment_name = assignment.get("name", "")
            self.log(f"✅ Đã mở bài: {self.selected_assignment_name}")
            
        except Exception as e:
            self.log(f"❌ Lỗi mở bài: {e}")
            messagebox.showerror("Lỗi", f"Lỗi mở bài: {e}")
        
    def load_config(self):
        """Load config from file"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
        
    def save_config(self):
        """Save config to file"""
        config = {
            "api_key": self.api_key_var.get(),
            "delay_min": self.delay_min_var.get(),
            "delay_max": self.delay_max_var.get(),
            "quiz_time": self.quiz_time_var.get(),
            "total_questions": self.total_questions_var.get(),
            "target_score": self.target_score_var.get(),
            "save_answers": self.save_answers_var.get(),
            "use_profile": self.use_profile_var.get(),
            "check_answer_files": self.check_answer_files_var.get(),
            "save_answer_files": self.save_answer_files_var.get(),
            "continue_on_timeout": self.continue_on_timeout_var.get(),
            "backend_url": self.backend_url_var.get(),
            "auto_detect": self.auto_detect_var.get(),
        }
        if self.remember_var.get():
            config["username"] = self.username_var.get()
            config["password"] = self.password_var.get()
            config["remember"] = True
        else:
            config["remember"] = False
            
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        self.log("✅ Đã lưu cài đặt!")
        
    def setup_driver(self):
        """Initialize Chrome driver with optional profile"""
        try:
            self.log("🌐 Đang khởi động Chrome...")
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            
            # Use Chrome profile if enabled
            if self.use_profile_var.get():
                # Use a dedicated profile folder for the tool
                profile_path = APP_DIR / "chrome_profile"
                profile_path.mkdir(exist_ok=True)
                options.add_argument(f"--user-data-dir={profile_path}")
                self.log(f"📁 Dùng profile: {profile_path.name}")
                self.log("💡 Lần đầu: Đăng nhập Google 1 lần, sau đó sẽ nhớ.")
            
            self.driver = uc.Chrome(options=options, version_main=142)
            self.log("✅ Chrome đã sẵn sàng!")
            return True
        except Exception as e:
            self.log(f"❌ Lỗi khởi động Chrome: {e}")
            return False
    
    def google_login(self):
        """Login with Google - opens browser and clicks Google button"""
        threading.Thread(target=self._do_google_login, daemon=True).start()
        
    def _do_google_login(self):
        """Google login thread"""
        try:
            if not self.driver:
                if not self.setup_driver():
                    return
                    
            self.log("🔵 Đăng nhập với Google...")
            self.status_var.set("🟡 Đăng nhập Google...")
            
            # Navigate to login page
            self.driver.get("https://app.onluyen.vn/")
            time.sleep(3)
            
            try:
                # Wait for login form
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".list-login-other"))
                )
                
                # Find and click Google login button
                # Based on the HTML: .list-login-other .item with text "Google"
                google_btn = self.driver.find_element(
                    By.XPATH, 
                    "//div[contains(@class, 'list-login-other')]//div[contains(@class, 'item')]//div[contains(text(), 'Google')]/parent::div"
                )
                
                # Store main window handle
                main_window = self.driver.current_window_handle
                
                google_btn.click()
                self.log("✅ Đã click nút Google Login")
                self.log("⏳ Vui lòng chọn tài khoản Google trong popup...")
                
                # Wait for popup or redirect
                time.sleep(2)
                
                # Check if a new window opened
                all_windows = self.driver.window_handles
                if len(all_windows) > 1:
                    # Switch to Google popup
                    for window in all_windows:
                        if window != main_window:
                            self.driver.switch_to.window(window)
                            self.log("🔵 Đã mở popup Google - Chọn tài khoản của bạn!")
                            break
                    
                    # Wait for popup to close (user selects account)
                    while len(self.driver.window_handles) > 1:
                        time.sleep(1)
                    
                    # Switch back to main window
                    self.driver.switch_to.window(main_window)
                    self.log("✅ Đã chọn tài khoản!")
                
                # Wait for redirect and check login status
                time.sleep(3)
                
                # Check if logged in successfully
                current_url = self.driver.current_url
                if "login" not in current_url.lower() or "app" in current_url.lower():
                    self.log("✅ Đăng nhập Google thành công!")
                    self.status_var.set("🟢 Đã đăng nhập")
                else:
                    self.log("⚠️ Chờ đăng nhập hoàn tất...")
                    # Wait a bit more for redirect
                    for i in range(10):
                        time.sleep(2)
                        if "login" not in self.driver.current_url.lower():
                            self.log("✅ Đăng nhập Google thành công!")
                            self.status_var.set("🟢 Đã đăng nhập")
                            return
                    self.log("⚠️ Không thể xác nhận đăng nhập. Vui lòng kiểm tra trình duyệt.")
                    self.status_var.set("🟡 Kiểm tra trình duyệt")
                    
            except TimeoutException:
                self.log("⚠️ Không tìm thấy form đăng nhập. Có thể đã đăng nhập sẵn.")
                self.status_var.set("🟢 Sẵn sàng")
            except Exception as e:
                self.log(f"⚠️ Lỗi: {e}")
                self.log("🔵 Vui lòng đăng nhập Google thủ công trong trình duyệt.")
                self.status_var.set("🟡 Đăng nhập thủ công")
                
        except Exception as e:
            self.log(f"❌ Lỗi: {e}")
            self.status_var.set("🔴 Lỗi")
            
    def auto_login(self):
        """Perform auto login"""
        username = self.username_var.get()
        password = self.password_var.get()
        
        if not username or not password:
            messagebox.showerror("Lỗi", "Vui lòng nhập tài khoản và mật khẩu!")
            return
            
        if self.remember_var.get():
            self.save_config()
            
        # Start login in thread
        threading.Thread(target=self._do_login, args=(username, password), daemon=True).start()
        
    def _do_login(self, username, password):
        """Login thread"""
        try:
            if not self.driver:
                if not self.setup_driver():
                    return
                    
            self.log("🔐 Đang đăng nhập...")
            self.status_var.set("🟡 Đang đăng nhập...")
            
            # Navigate to login page
            self.driver.get("https://app.onluyen.vn/")
            time.sleep(3)
            
            # Try to find and fill login form
            try:
                # Wait for login form to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".form-login"))
                )
                self.log("✅ Đã tìm thấy form đăng nhập")
                
                # Find username field (inside .input-name, type text)
                username_field = self.driver.find_element(
                    By.CSS_SELECTOR, ".form-login .input-name input[type='text']"
                )
                username_field.clear()
                username_field.send_keys(username)
                self.log(f"✅ Đã điền tài khoản: {username}")
                
                time.sleep(0.3)
                
                # Find password field (inside .input-name, type password)
                password_field = self.driver.find_element(
                    By.CSS_SELECTOR, ".form-login .input-name input[type='password']"
                )
                password_field.clear()
                password_field.send_keys(password)
                self.log("✅ Đã điền mật khẩu")
                
                time.sleep(0.5)
                
                # Find and click login button (.btn-login button)
                login_btn = self.driver.find_element(By.CSS_SELECTOR, ".btn-login button")
                login_btn.click()
                self.log("🔄 Đang xử lý đăng nhập...")
                
                time.sleep(4)
                
                # Check if login successful by checking URL or element
                current_url = self.driver.current_url
                if "login" not in current_url.lower():
                    self.log("✅ Đăng nhập thành công!")
                    self.status_var.set("🟢 Đã đăng nhập")
                else:
                    # Check for error message
                    try:
                        error_elem = self.driver.find_element(By.CSS_SELECTOR, ".field-text-error")
                        error_text = error_elem.text.strip()
                        if error_text:
                            self.log(f"❌ Lỗi đăng nhập: {error_text}")
                            self.status_var.set("🔴 Đăng nhập thất bại")
                        else:
                            self.log("✅ Đăng nhập thành công!")
                            self.status_var.set("🟢 Đã đăng nhập")
                    except:
                        self.log("✅ Đăng nhập thành công!")
                        self.status_var.set("🟢 Đã đăng nhập")
                
            except TimeoutException:
                self.log("⚠️ Không tìm thấy form đăng nhập. Có thể đã đăng nhập sẵn.")
                self.status_var.set("🟢 Sẵn sàng")
            except Exception as e:
                self.log(f"⚠️ Lỗi đăng nhập: {e}")
                self.log("Vui lòng đăng nhập thủ công rồi nhấn 'Bắt Đầu Giải'")
                self.status_var.set("🟡 Chờ đăng nhập thủ công")
                
        except Exception as e:
            self.log(f"❌ Lỗi: {e}")
            self.status_var.set("🔴 Lỗi")
            
    def check_link_verification(self):
        """Check if user has passed the verification link (with 3-day free trial)"""
        import requests
        import webbrowser
        from datetime import datetime, timedelta
        
        FREE_TRIAL_DAYS = 3
        
        # Check if still in free trial period
        first_use = self.config.get("first_use_date")
        if not first_use:
            # First time using - start trial
            first_use = datetime.now().isoformat()
            self.config["first_use_date"] = first_use
            self.save_config()
            self.log(f"🎁 Bắt đầu thời gian dùng thử {FREE_TRIAL_DAYS} ngày miễn phí!")
        
        # Parse first use date
        try:
            first_use_dt = datetime.fromisoformat(first_use)
            trial_end = first_use_dt + timedelta(days=FREE_TRIAL_DAYS)
            now = datetime.now()
            
            if now < trial_end:
                # Still in trial period
                remaining = trial_end - now
                days_left = remaining.days
                hours_left = remaining.seconds // 3600
                self.log(f"🎁 Dùng thử miễn phí: còn {days_left} ngày {hours_left} giờ")
                return True  # No need to verify during trial
        except:
            pass  # If date parsing fails, require verification
        
        # Trial expired - require link verification
        hwid = license_utils.get_hwid()
        server_url = license_utils.SERVER_URL
        
        try:
            # Check status
            resp = requests.post(f"{server_url}/check_verification", json={"hwid": hwid}, timeout=5)
            if resp.status_code == 200 and resp.json().get("verified"):
                remaining_mins = resp.json().get("remaining_minutes", 0)
                self.log(f"✅ Đã xác thực (còn {remaining_mins} phút)")
                return True
                
            # Not verified, ask user
            if messagebox.askyesno("Hết Thời Gian Dùng Thử", 
                f"Thời gian dùng thử {FREE_TRIAL_DAYS} ngày đã hết!\n\n"
                "Bạn cần vượt link rút gọn để tiếp tục sử dụng tool trong 4 giờ tới.\n\n"
                "Nhấn YES để lấy link và mở trình duyệt."):
                # Get link
                self.log("⏳ Đang lấy link xác thực...")
                resp = requests.post(f"{server_url}/get_link", json={"hwid": hwid}, timeout=10)
                
                if resp.status_code == 200:
                    short_url = resp.json().get("url")
                    if short_url:
                        self.log(f"🔗 Link: {short_url}")
                        webbrowser.open(short_url)
                        
                        # Show dialog to wait
                        msg_box = tk.Toplevel(self.root)
                        msg_box.title("Đang Chờ Xác Thực")
                        msg_box.geometry("400x200")
                        msg_box.transient(self.root)
                        msg_box.grab_set()
                        
                        ttk.Label(msg_box, text="Vui lòng vượt link trong trình duyệt...", font=("Segoe UI", 12)).pack(pady=20)
                        
                        status_lbl = ttk.Label(msg_box, text="Đang chờ...", foreground="#f59e0b")
                        status_lbl.pack(pady=5)
                        
                        result = {"verified": False}
                        
                        def check_again():
                            try:
                                r = requests.post(f"{server_url}/check_verification", json={"hwid": hwid}, timeout=5)
                                if r.status_code == 200 and r.json().get("verified"):
                                    status_lbl.config(text="✅ Đã xác thực thành công!", foreground="#10b981")
                                    result["verified"] = True
                                    msg_box.after(1000, msg_box.destroy)
                                else:
                                    status_lbl.config(text="❌ Chưa xác thực xong. Hãy thử lại.", foreground="#ef4444")
                            except:
                                status_lbl.config(text="❌ Lỗi kết nối server", foreground="#ef4444")
                        
                        tk.Button(msg_box, text="Tôi đã vượt link xong", 
                                 bg="#e94560", fg="white", font=("Segoe UI", 10, "bold"),
                                 command=check_again).pack(pady=20)
                                 
                        self.root.wait_window(msg_box)
                        return result["verified"]
                    else:
                        messagebox.showerror("Lỗi", "Không lấy được link rút gọn!")
                else:
                    messagebox.showerror("Lỗi", f"Lỗi server: {resp.text}")
            
            return False
            
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể kết nối server xác thực: {e}")
            return False
            
    def start_automation(self):
        """Start quiz solving automation"""
        api_key = self.api_key_var.get()
        if not api_key:
            messagebox.showerror("Lỗi", "Vui lòng nhập Gemini API Key!")
            return
            
        if not self.driver:
            messagebox.showinfo("Thông báo", "Vui lòng đăng nhập trước!")
            return
            
        # Check Link Verification
        if not self.check_link_verification():
            return
            
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        self.is_running = True
        self.stop_flag = False
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_var.set("🟢 Đang giải bài...")
        
        # Start automation thread
        self.automation_thread = threading.Thread(target=self._run_automation, daemon=True)
        self.automation_thread.start()
        
    def stop_automation(self):
        """Stop automation"""
        self.stop_flag = True
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("⏹ Đã dừng")
        self.log("⏹ Đã dừng giải bài")
    
    def _run_automation(self):
        """Main automation loop with advanced quiz solving"""
        from quiz_logic_advanced import solve_quiz
        import random
        
        config = {
            "api_key": self.api_key_var.get(),
            "backend_url": self.backend_url_var.get(),
            "quiz_time": int(self.quiz_time_var.get()),
            "check_answer_files": self.check_answer_files_var.get(),
            "save_answers": self.save_answer_files_var.get(),
            "continue_on_timeout": self.continue_on_timeout_var.get(),
            "auto_detect": self.auto_detect_var.get(),
            "selected_assignment_name": self.selected_assignment_name,
        }
        
        # Run solve_quiz from advanced logic
        success = solve_quiz(self.driver, config, self.log)
        
        if success:
            self.status_var.set("✅ Hoàn thành")
        else:
            self.status_var.set("❌ Lỗi")
        
    def _click_submit_button(self):
        """Find and click the submit/next button"""
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
                self.log("✅ Đã click 'Trả lời'")
                return True
            except:
                continue
        
        self.log("⚠️ Không tìm thấy nút 'Trả lời'")
        return False
    
    def _fake_mouse_activity(self):
        """Simulate mouse movement inside browser to avoid detection"""
        try:
            # Get window size
            window_size = self.driver.get_window_size()
            width = window_size['width']
            height = window_size['height']
            
            # Random position within viewport (avoiding edges)
            x = random.randint(100, max(200, width - 200))
            y = random.randint(100, max(200, height - 200))
            
            # Move mouse using JavaScript (simulates movement)
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
            
            # Sometimes also trigger a small scroll
            if random.random() < 0.3:
                scroll_amount = random.randint(-50, 50)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                
        except:
            pass  # Silently ignore errors
        
    def on_closing(self):
        """Handle window close"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    app = QuizSolverApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
