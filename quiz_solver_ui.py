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
import undetected_chromedriver as uc
# Config file path
CONFIG_FILE = Path(__file__).parent / "config.json"

class QuizSolverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quiz Solver - Ôn Luyện VN")
        self.root.geometry("800x750")  # Larger default size
        self.root.minsize(600, 500)    # Minimum size
        self.root.configure(bg="#1a1a2e")
        
        # State
        self.driver = None
        self.is_running = False
        self.stop_flag = False
        self.automation_thread = None
        
        # Load config
        self.config = self.load_config()
        
        # Setup UI
        self.setup_styles()
        self.create_widgets()
        
        # Check License (after UI is ready)
        self.root.after(100, self.check_license)
        
        # Check for updates
        self.root.after(500, self.check_for_updates)

    # Tool version
    TOOL_VERSION = "2.0.0"
    
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
            current_dir = Path(__file__).parent
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

    def check_license(self):
        """Check if valid license exists, otherwise prompt user"""
        hwid = license_utils.get_hwid()
        saved_key = self.config.get("license_key", "")
        
        is_valid = False
        if saved_key:
            # Verify with server
            valid, msg = license_utils.verify_key(hwid, saved_key)
            if valid:
                is_valid = True
            else:
                print(f"License check failed: {msg}")
                
        if not is_valid:
            self.show_activation_dialog(hwid)
            
    def show_activation_dialog(self, hwid):
        """Show modal dialog for activation"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Kích Hoạt Bản Quyền")
        dialog.geometry("500x300")
        dialog.configure(bg="#1a1a2e")
        dialog.transient(self.root)
        dialog.grab_set()  # Modal
        
        # Center dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (500 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (300 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # UI Elements
        ttk.Label(dialog, text="🔒 Yêu Cầu Kích Hoạt", 
                 font=("Segoe UI", 16, "bold"), 
                 background="#1a1a2e", foreground="#e94560").pack(pady=20)
                 
        ttk.Label(dialog, text="Mã máy (HWID):", 
                 background="#1a1a2e", foreground="white").pack()
                 
        hwid_entry = ttk.Entry(dialog, width=50, justify="center")
        hwid_entry.insert(0, hwid)
        hwid_entry.config(state="readonly")
        hwid_entry.pack(pady=5)
        
        ttk.Label(dialog, text="Nhập Key Kích Hoạt:", 
                 background="#1a1a2e", foreground="white").pack(pady=(15, 5))
                 
        key_var = tk.StringVar()
        key_entry = ttk.Entry(dialog, textvariable=key_var, width=30, justify="center", font=("Consolas", 12))
        key_entry.pack(pady=5)
        
        status_label = ttk.Label(dialog, text="", background="#1a1a2e", foreground="#ef4444")
        status_label.pack(pady=5)
        
        def activate():
            key = key_var.get().strip()
            if not key:
                status_label.config(text="Vui lòng nhập Key!")
                return
                
            status_label.config(text="Đang kiểm tra...", foreground="#fbbf24")
            dialog.update()
            
            valid, msg = license_utils.verify_key(hwid, key)
            if valid:
                status_label.config(text="✅ Kích hoạt thành công!", foreground="#4ade80")
                dialog.update()
                time.sleep(1)
                
                # Save key
                self.config["license_key"] = key
                self.save_config()
                dialog.destroy()
            else:
                status_label.config(text=f"❌ Lỗi: {msg}", foreground="#ef4444")
        
        tk.Button(dialog, text="Kích Hoạt Ngay", 
                 bg="#e94560", fg="white", font=("Segoe UI", 10, "bold"),
                 relief=tk.FLAT, padx=20, pady=5,
                 command=activate).pack(pady=20)
                 
        # Prevent closing without activation
        def on_close():
            if "license_key" not in self.config:
                self.root.destroy()
            else:
                dialog.destroy()
                
        dialog.protocol("WM_DELETE_WINDOW", on_close)
        
        # Wait for dialog to close
        self.root.wait_window(dialog)

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
        # Main container
        main_frame = ttk.Frame(self.root, style="Dark.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title = ttk.Label(main_frame, text="🎯 Quiz Solver - Ôn Luyện VN", style="Title.TLabel")
        title.pack(pady=(0, 20))
        
        # Login Section
        self.create_login_section(main_frame)
        
        # API Key Section
        self.create_api_section(main_frame)
        
        # Control Section
        self.create_control_section(main_frame)
        
        # Log Section
        self.create_log_section(main_frame)
        
    def create_login_section(self, parent):
        """Create login form section"""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill=tk.X, pady=(0, 15))
        
        # Header
        header = ttk.Label(frame, text="🔐 Đăng Nhập", style="Subtitle.TLabel")
        header.pack(anchor=tk.W, padx=15, pady=(15, 10))
        
        # Username
        user_frame = ttk.Frame(frame, style="Card.TFrame")
        user_frame.pack(fill=tk.X, padx=15, pady=5)
        
        ttk.Label(user_frame, text="Tài khoản:", style="Normal.TLabel", width=12).pack(side=tk.LEFT)
        self.username_var = tk.StringVar(value=self.config.get("username", ""))
        self.username_entry = ttk.Entry(user_frame, textvariable=self.username_var, width=40)
        self.username_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # Password
        pass_frame = ttk.Frame(frame, style="Card.TFrame")
        pass_frame.pack(fill=tk.X, padx=15, pady=5)
        
        ttk.Label(pass_frame, text="Mật khẩu:", style="Normal.TLabel", width=12).pack(side=tk.LEFT)
        self.password_var = tk.StringVar(value=self.config.get("password", ""))
        self.password_entry = ttk.Entry(pass_frame, textvariable=self.password_var, width=40, show="*")
        self.password_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # Remember checkbox & Login buttons
        btn_frame = ttk.Frame(frame, style="Card.TFrame")
        btn_frame.pack(fill=tk.X, padx=15, pady=(10, 15))
        
        self.remember_var = tk.BooleanVar(value=self.config.get("remember", False))
        remember_cb = ttk.Checkbutton(btn_frame, text="Ghi nhớ", variable=self.remember_var)
        remember_cb.pack(side=tk.LEFT)
        
        # Google login button
        google_btn = tk.Button(btn_frame, text="� Google", 
                              bg="#4285f4", fg="white",
                              font=("Segoe UI", 10, "bold"),
                              relief=tk.FLAT, padx=15, pady=5,
                              command=self.google_login)
        google_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Regular login button
        login_btn = tk.Button(btn_frame, text="🚀 Đăng Nhập", 
                             bg=self.accent_light, fg="white",
                             font=("Segoe UI", 10, "bold"),
                             relief=tk.FLAT, padx=15, pady=5,
                             command=self.auto_login)
        login_btn.pack(side=tk.RIGHT)
        
    def create_api_section(self, parent):
        """Create API key and timing settings section"""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill=tk.X, pady=(0, 15))
        
        header = ttk.Label(frame, text="⚙️ Cài Đặt", style="Subtitle.TLabel")
        header.pack(anchor=tk.W, padx=15, pady=(15, 10))
        
        # API Key row
        api_frame = ttk.Frame(frame, style="Card.TFrame")
        api_frame.pack(fill=tk.X, padx=15, pady=(0, 8))
        
        ttk.Label(api_frame, text="Gemini API:", style="Normal.TLabel", width=14).pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(value=self.config.get("api_key", ""))
        self.api_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, width=35, show="*")
        self.api_entry.pack(side=tk.LEFT, padx=(10, 10))
        
        save_btn = tk.Button(api_frame, text="💾 Lưu", 
                            bg=self.accent, fg="white",
                            font=("Segoe UI", 9),
                            relief=tk.FLAT, padx=15,
                            command=self.save_config)
        save_btn.pack(side=tk.LEFT)
        
        # Timing settings row 1: delay per question
        timing_frame1 = ttk.Frame(frame, style="Card.TFrame")
        timing_frame1.pack(fill=tk.X, padx=15, pady=(0, 8))
        
        ttk.Label(timing_frame1, text="Delay mỗi câu:", style="Normal.TLabel", width=14).pack(side=tk.LEFT)
        self.delay_min_var = tk.StringVar(value=self.config.get("delay_min", "3"))
        self.delay_max_var = tk.StringVar(value=self.config.get("delay_max", "8"))
        
        ttk.Entry(timing_frame1, textvariable=self.delay_min_var, width=5).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(timing_frame1, text=" - ", style="Normal.TLabel").pack(side=tk.LEFT)
        ttk.Entry(timing_frame1, textvariable=self.delay_max_var, width=5).pack(side=tk.LEFT)
        ttk.Label(timing_frame1, text=" giây", style="Normal.TLabel").pack(side=tk.LEFT, padx=(5, 0))
        
        # Timing settings row 2: total quiz time
        timing_frame2 = ttk.Frame(frame, style="Card.TFrame")
        timing_frame2.pack(fill=tk.X, padx=15, pady=(0, 8))
        
        ttk.Label(timing_frame2, text="Thời gian làm:", style="Normal.TLabel", width=14).pack(side=tk.LEFT)
        self.quiz_time_var = tk.StringVar(value=self.config.get("quiz_time", "30"))
        
        ttk.Entry(timing_frame2, textvariable=self.quiz_time_var, width=5).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(timing_frame2, text=" phút (10-90)", style="Normal.TLabel").pack(side=tk.LEFT, padx=(5, 0))
        
        # AI vs Random settings
        ai_frame = ttk.Frame(frame, style="Card.TFrame")
        ai_frame.pack(fill=tk.X, padx=15, pady=(0, 8))
        
        ttk.Label(ai_frame, text="Số câu AI làm:", style="Normal.TLabel", width=14).pack(side=tk.LEFT)
        self.ai_count_var = tk.StringVar(value=self.config.get("ai_count", "0"))  # 0 = all
        ttk.Entry(ai_frame, textvariable=self.ai_count_var, width=5).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(ai_frame, text=" (0 = tất cả)", style="Normal.TLabel").pack(side=tk.LEFT, padx=(5, 0))
        
        random_frame = ttk.Frame(frame, style="Card.TFrame")
        random_frame.pack(fill=tk.X, padx=15, pady=(0, 8))
        
        ttk.Label(random_frame, text="Số câu random:", style="Normal.TLabel", width=14).pack(side=tk.LEFT)
        self.random_count_var = tk.StringVar(value=self.config.get("random_count", "0"))
        ttk.Entry(random_frame, textvariable=self.random_count_var, width=5).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(random_frame, text=" câu cuối sẽ random", style="Normal.TLabel").pack(side=tk.LEFT, padx=(5, 0))
        
        # Save answers checkbox
        save_frame = ttk.Frame(frame, style="Card.TFrame")
        save_frame.pack(fill=tk.X, padx=15, pady=(0, 8))
        
        self.save_answers_var = tk.BooleanVar(value=self.config.get("save_answers", True))
        save_cb = ttk.Checkbutton(save_frame, text="📝 Lưu câu hỏi & đáp án vào file", variable=self.save_answers_var)
        save_cb.pack(side=tk.LEFT)
        
        # Use Chrome profile checkbox
        profile_frame = ttk.Frame(frame, style="Card.TFrame")
        profile_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        self.use_profile_var = tk.BooleanVar(value=self.config.get("use_profile", True))
        profile_cb = ttk.Checkbutton(profile_frame, text="🔵 Dùng Chrome Profile (đã đăng nhập Google sẵn)", variable=self.use_profile_var)
        profile_cb.pack(side=tk.LEFT)
        
    def create_control_section(self, parent):
        """Create start/stop controls"""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill=tk.X, pady=(0, 15))
        
        header = ttk.Label(frame, text="🎮 Điều Khiển", style="Subtitle.TLabel")
        header.pack(anchor=tk.W, padx=15, pady=(15, 10))
        
        ctrl_frame = ttk.Frame(frame, style="Card.TFrame")
        ctrl_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        # Status
        ttk.Label(ctrl_frame, text="Trạng thái:", style="Normal.TLabel").pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="⚪ Chờ đăng nhập")
        self.status_label = ttk.Label(ctrl_frame, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Buttons
        self.stop_btn = tk.Button(ctrl_frame, text="⏹ Dừng",
                                 bg="#ef4444", fg="white",
                                 font=("Segoe UI", 10, "bold"),
                                 relief=tk.FLAT, padx=20, pady=5,
                                 command=self.stop_automation,
                                 state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        self.start_btn = tk.Button(ctrl_frame, text="▶ Bắt Đầu Giải",
                                  bg="#22c55e", fg="white",
                                  font=("Segoe UI", 10, "bold"),
                                  relief=tk.FLAT, padx=20, pady=5,
                                  command=self.start_automation)
        self.start_btn.pack(side=tk.RIGHT)
        
    def create_log_section(self, parent):
        """Create log output section"""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill=tk.BOTH, expand=True)
        
        header_frame = ttk.Frame(frame, style="Card.TFrame")
        header_frame.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        ttk.Label(header_frame, text="📋 Nhật Ký", style="Subtitle.TLabel").pack(side=tk.LEFT)
        
        clear_btn = tk.Button(header_frame, text="🗑 Xóa",
                             bg=self.accent, fg="white",
                             font=("Segoe UI", 9),
                             relief=tk.FLAT, padx=10,
                             command=self.clear_log)
        clear_btn.pack(side=tk.RIGHT)
        
        # Log text area - larger height
        self.log_text = scrolledtext.ScrolledText(frame, 
                                                  height=15,
                                                  bg="#0d1117",
                                                  fg="#58a6ff",
                                                  font=("Consolas", 10),
                                                  insertbackground="white")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
    def log(self, message):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clear_log(self):
        """Clear log area"""
        self.log_text.delete(1.0, tk.END)
        
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
            "ai_count": self.ai_count_var.get(),
            "random_count": self.random_count_var.get(),
            "save_answers": self.save_answers_var.get(),
            "use_profile": self.use_profile_var.get(),
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
                profile_path = Path(__file__).parent / "chrome_profile"
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
        """Main automation loop with timing and logging"""
        from quiz_solver import (
            get_gemini_response, 
            get_true_false_response, 
            get_short_answer_response
        )

        
        # Get timing settings
        try:
            delay_min = int(self.delay_min_var.get())
            delay_max = int(self.delay_max_var.get())
        except:
            delay_min, delay_max = 3, 8
            
        try:
            quiz_time_minutes = int(self.quiz_time_var.get())
            quiz_time_minutes = max(10, min(90, quiz_time_minutes))  # Clamp 10-90
        except:
            quiz_time_minutes = 30
        
        # AI and random settings
        try:
            ai_count = int(self.ai_count_var.get())  # 0 = all
        except:
            ai_count = 0
            
        try:
            random_count = int(self.random_count_var.get())
        except:
            random_count = 0
            
        save_answers = self.save_answers_var.get()
        
        # Setup logging file
        log_file = None
        if save_answers:
            log_filename = Path(__file__).parent / f"quiz_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            log_file = open(log_filename, 'w', encoding='utf-8')
            log_file.write(f"=== Quiz Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
            self.log(f"📝 Lưu đáp án vào: {log_filename.name}")
        
        start_time = time.time()
        end_time = start_time + (quiz_time_minutes * 60)
        question_count = 0
        ai_answered = 0  # Track AI answered questions
        
        self.log("🚀 Bắt đầu giải bài tự động!")
        self.log(f"⏱️ Thời gian làm: {quiz_time_minutes} phút")
        self.log(f"⏳ Delay mỗi câu: {delay_min}-{delay_max} giây")
        if ai_count > 0:
            self.log(f"🤖 AI sẽ làm: {ai_count} câu đầu")
        if random_count > 0:
            self.log(f"🎲 Random: {random_count} câu cuối")
        self.log("📌 Hãy mở một bài quiz trên trình duyệt")
        
        while not self.stop_flag:
            # Check time limit
            if time.time() >= end_time:
                self.log(f"⏰ Hết thời gian ({quiz_time_minutes} phút)!")
                break
                
            try:
                # Wait for question to load
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".question-name"))
                    )
                except TimeoutException:
                    time.sleep(1)
                    continue
                
                question_count += 1
                remaining_time = int((end_time - time.time()) / 60)
                self.log(f"--- Câu {question_count} (còn {remaining_time} phút) ---")
                
                # Determine if using AI or random for this question
                use_ai = True
                if ai_count > 0 and ai_answered >= ai_count:
                    use_ai = False
                    self.log("🎲 Câu này sẽ random (đã đủ số câu AI)")
                
                # Get question text for logging
                question_text = ""
                try:
                    question_elem = self.driver.find_element(By.CSS_SELECTOR, ".question-name")
                    question_text = question_elem.text.strip()[:200]  # First 200 chars
                except:
                    pass
                    
                # Take screenshot
                screenshot_png = self.driver.get_screenshot_as_png()
                image_data = screenshot_png
                
                # Detect question type and solve
                short_answer_inputs = self.driver.find_elements(By.CSS_SELECTOR, ".answer-input input[type='text']")
                if not short_answer_inputs:
                    short_answer_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[id^='mathplay-answer']")
                    
                true_false_containers = self.driver.find_elements(By.CSS_SELECTOR, ".true-false")
                
                answer_for_log = ""
                explanation_for_log = ""
                question_type = ""
                
                if short_answer_inputs:
                    # SHORT ANSWER
                    question_type = "Trả lời ngắn"
                    self.log(f"📝 Loại câu hỏi: {question_type}")
                    
                    if use_ai:
                        ai_answered += 1
                        # Get answer with explanation
                        result = get_short_answer_response(image_data, with_explanation=True)
                        
                        if result and isinstance(result, tuple):
                            answer, explanation = result
                        else:
                            answer, explanation = result, ""
                        
                        if answer:
                            answer_for_log = answer
                            explanation_for_log = explanation
                            self.log(f"💡 Đáp án: {answer}")
                            input_field = short_answer_inputs[0]
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", input_field)
                            input_field.clear()
                            input_field.send_keys(answer)
                        else:
                            self.log("⚠️ Không tìm được đáp án")
                    else:
                        # Random answer for short answer - just type a random number

                        random_answer = str(random.randint(1, 100))
                        answer_for_log = f"RANDOM: {random_answer}"
                        self.log(f"🎲 Random: {random_answer}")
                        input_field = short_answer_inputs[0]
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", input_field)
                        input_field.clear()
                        input_field.send_keys(random_answer)
                        
                elif true_false_containers:
                    # TRUE/FALSE
                    question_type = "Đúng/Sai"
                    self.log(f"✅❌ Loại câu hỏi: {question_type} ({len(true_false_containers)} câu)")
                    
                    if use_ai:
                        ai_answered += 1
                        # Get answers with explanation
                        result = get_true_false_response(image_data, len(true_false_containers), with_explanation=True)
                        
                        if result and isinstance(result, tuple):
                            answers, explanation = result
                        else:
                            answers, explanation = result, ""
                    else:
                        # Random true/false answers

                        answers = [random.choice(["true", "false"]) for _ in true_false_containers]
                        explanation = "RANDOM"
                        self.log("🎲 Random đáp án...")
                    
                    if answers:
                        answer_for_log = ", ".join([f"{chr(ord('a')+i)}={'Đ' if a=='true' else 'S'}" for i, a in enumerate(answers)])
                        explanation_for_log = explanation
                        for idx, tf_container in enumerate(true_false_containers):
                            answer = answers[idx] if idx < len(answers) else "true"
                            letter = chr(ord('a') + idx)
                            
                            try:
                                if answer == "true":
                                    radio = tf_container.find_element(By.CSS_SELECTOR, "input[value='true']")
                                    label_text = "Đúng"
                                else:
                                    radio = tf_container.find_element(By.CSS_SELECTOR, "input[value='false']")
                                    label_text = "Sai"
                                    
                                radio_id = radio.get_attribute("id")
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", radio)
                                
                                try:
                                    label = tf_container.find_element(By.CSS_SELECTOR, f"label[for='{radio_id}']")
                                    label.click()
                                except:
                                    self.driver.execute_script("arguments[0].click();", radio)
                                    
                                self.log(f"  Câu {letter}: {label_text}")
                            except Exception as e:
                                self.log(f"  ⚠️ Lỗi câu {letter}: {e}")
                else:
                    # MULTIPLE CHOICE
                    options_elems = self.driver.find_elements(By.CSS_SELECTOR, ".question-option")
                    if options_elems:
                        question_type = "Trắc nghiệm"
                        self.log(f"🔘 Loại câu hỏi: {question_type} ({len(options_elems)} đáp án)")
                        
                        if use_ai:
                            ai_answered += 1
                            # Get answer with explanation
                            result = get_gemini_response(image_data, with_explanation=True)
                            
                            if result and isinstance(result, tuple):
                                answer_letter, explanation = result
                            else:
                                answer_letter, explanation = result, ""
                        else:
                            # Random answer for multiple choice

                            answer_letter = random.choice(["A", "B", "C", "D"][:len(options_elems)])
                            explanation = "RANDOM"
                            self.log(f"🎲 Random: {answer_letter}")
                        
                        if answer_letter and answer_letter in "ABCD":
                            answer_for_log = answer_letter
                            explanation_for_log = explanation
                            if use_ai:
                                self.log(f"💡 Đáp án: {answer_letter}")
                            answer_index = ord(answer_letter) - ord('A')
                            
                            if answer_index < len(options_elems):
                                target_option = options_elems[answer_index]
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", target_option)
                                time.sleep(0.5)
                                
                                try:
                                    target_option.click()
                                except:
                                    self.driver.execute_script("arguments[0].click();", target_option)
                        else:
                            self.log("⚠️ Không tìm được đáp án")
                    else:
                        self.log("⚠️ Không tìm thấy options")
                        time.sleep(2)
                        continue
                
                # Log to file
                if log_file and answer_for_log:
                    log_file.write(f"Câu {question_count}: [{question_type}]\n")
                    log_file.write(f"  Câu hỏi: {question_text}\n")
                    log_file.write(f"  Đáp án: {answer_for_log}\n")
                    if explanation_for_log:
                        log_file.write(f"  Giải thích: {explanation_for_log}\n")
                    log_file.write("\n" + "-"*50 + "\n\n")
                    log_file.flush()
                        
                # Click "Trả lời" button
                self._click_submit_button()
                
                # Random delay
                delay = random.uniform(delay_min, delay_max)
                self.log(f"⏳ Chờ {delay:.1f} giây...")
                time.sleep(delay)
                
            except Exception as e:
                self.log(f"❌ Lỗi: {e}")
                time.sleep(2)
        
        # Cleanup
        if log_file:
            elapsed = (time.time() - start_time) / 60
            log_file.write(f"\n=== Hoàn thành ===\n")
            log_file.write(f"Tổng số câu: {question_count}\n")
            log_file.write(f"Thời gian: {elapsed:.1f} phút\n")
            log_file.close()
            self.log(f"📝 Đã lưu {question_count} câu vào file!")
            
        self.log(f"🏁 Kết thúc: {question_count} câu trong {(time.time() - start_time)/60:.1f} phút")
        
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
