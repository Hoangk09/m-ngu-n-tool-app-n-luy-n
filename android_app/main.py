"""
Quiz Solver - Main Android App with Floating Overlay
======================================================
Floating popup hiện trạng thái, nút Bắt đầu/Dừng
Chạy trên app Ôn Luyện native (không phải web)
"""

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.utils import platform

import os
import time

# Import our modules
from solver import GeminiSolver
from accessibility import get_accessibility_helper

# Android specific imports
if platform == 'android':
    from android.permissions import request_permissions, Permission
    from android import activity
    from jnius import autoclass
    
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
    
    ANDROID = True
else:
    ANDROID = False
    print("Desktop mode - Android features disabled")


class FloatingPanel(FloatLayout):
    """Floating overlay panel with controls"""
    
    status = StringProperty("San sang")
    is_running = BooleanProperty(False)
    solved_count = NumericProperty(0)
    
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app = app_ref
        
        # Panel size and position
        self.size_hint = (None, None)
        self.size = (300, 220)
        self.pos = (10, Window.height - 250)
        
        # Create background
        with self.canvas.before:
            Color(0.12, 0.12, 0.18, 0.95)
            self.bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self._update_bg, size=self._update_bg)
        
        # Main container
        container = BoxLayout(
            orientation='vertical',
            padding=[12, 10, 12, 10],
            spacing=8,
            size=self.size,
            pos=self.pos
        )
        self.bind(pos=self._update_container_pos)
        self.container = container
        
        # Header with title and minimize button
        header = BoxLayout(size_hint_y=0.15)
        
        title = Label(
            text='Quiz Solver',
            font_size='18sp',
            bold=True,
            color=(0.3, 0.8, 1, 1),
            halign='left'
        )
        header.add_widget(title)
        
        btn_minimize = Button(
            text='-',
            size_hint=(None, None),
            size=(35, 28),
            background_color=(0.4, 0.4, 0.5, 1),
            font_size='18sp'
        )
        btn_minimize.bind(on_press=self.toggle_minimize)
        header.add_widget(btn_minimize)
        
        container.add_widget(header)
        
        # Status display
        self.status_box = BoxLayout(size_hint_y=0.15)
        self.status_label = Label(
            text=self.status,
            font_size='14sp',
            color=(0.7, 1, 0.7, 1)
        )
        self.status_box.add_widget(self.status_label)
        container.add_widget(self.status_box)
        
        # Counter
        self.counter_label = Label(
            text=f'Da giai: {self.solved_count} cau',
            font_size='12sp',
            size_hint_y=0.1,
            color=(0.8, 0.8, 0.8, 1)
        )
        container.add_widget(self.counter_label)
        
        # Control buttons
        buttons = BoxLayout(size_hint_y=0.25, spacing=8)
        
        self.btn_start = Button(
            text='BAT DAU',
            background_color=(0.2, 0.7, 0.3, 1),
            font_size='16sp',
            bold=True
        )
        self.btn_start.bind(on_press=self.on_start_press)
        buttons.add_widget(self.btn_start)
        
        self.btn_stop = Button(
            text='DUNG',
            background_color=(0.7, 0.3, 0.2, 1),
            font_size='16sp',
            bold=True,
            disabled=True
        )
        self.btn_stop.bind(on_press=self.on_stop_press)
        buttons.add_widget(self.btn_stop)
        
        container.add_widget(buttons)
        
        # Action buttons row
        actions = BoxLayout(size_hint_y=0.18, spacing=5)
        
        btn_settings = Button(
            text='Cai dat',
            background_color=(0.4, 0.4, 0.5, 1),
            font_size='12sp'
        )
        btn_settings.bind(on_press=self.open_settings)
        actions.add_widget(btn_settings)
        
        btn_access = Button(
            text='Accessibility',
            background_color=(0.5, 0.4, 0.3, 1),
            font_size='12sp'
        )
        btn_access.bind(on_press=self.open_accessibility)
        actions.add_widget(btn_access)
        
        container.add_widget(actions)
        
        # Log area
        self.log_label = Label(
            text='San sang. Mo app On Luyen roi bat dau.',
            font_size='11sp',
            size_hint_y=0.17,
            color=(0.6, 0.6, 0.6, 1),
            halign='left',
            valign='top'
        )
        self.log_label.bind(size=self.log_label.setter('text_size'))
        container.add_widget(self.log_label)
        
        self.add_widget(container)
        
        # Make panel draggable
        self.dragging = False
        self.drag_offset = (0, 0)
        
        # Minimized state
        self.minimized = False
        self.full_size = self.size
    
    def _update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size
    
    def _update_container_pos(self, *args):
        self.container.pos = self.pos
        self.container.size = self.size
    
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.dragging = True
            self.drag_offset = (touch.x - self.x, touch.y - self.y)
            return True
        return super().on_touch_down(touch)
    
    def on_touch_move(self, touch):
        if self.dragging:
            new_x = touch.x - self.drag_offset[0]
            new_y = touch.y - self.drag_offset[1]
            # Keep within screen bounds
            self.x = max(0, min(new_x, Window.width - self.width))
            self.y = max(0, min(new_y, Window.height - self.height))
            return True
        return super().on_touch_move(touch)
    
    def on_touch_up(self, touch):
        self.dragging = False
        return super().on_touch_up(touch)
    
    def toggle_minimize(self, instance):
        """Toggle between minimized and full view"""
        if self.minimized:
            # Restore
            self.size = self.full_size
            self.container.opacity = 1
            instance.text = '-'
            self.minimized = False
        else:
            # Minimize
            self.full_size = self.size
            self.size = (60, 60)
            self.container.opacity = 0
            instance.text = '+'
            self.minimized = True
    
    def log(self, message):
        """Add log message"""
        self.log_label.text = message
        print(f"[Panel] {message}")
    
    def update_status(self, status, color=(0.7, 1, 0.7, 1)):
        """Update status display"""
        self.status = status
        self.status_label.text = status
        self.status_label.color = color
    
    def on_start_press(self, instance):
        """Handle start button press"""
        self.start_solving()
    
    def on_stop_press(self, instance):
        """Handle stop button press"""
        self.stop_solving()
    
    def start_solving(self):
        """Start the auto-solve loop"""
        # Check accessibility service
        helper = get_accessibility_helper()
        
        if not helper.is_enabled():
            self.log("Bat Accessibility Service truoc!")
            self.update_status("Can bat Accessibility", (1, 0.5, 0.5, 1))
            return
        
        # Check Gemini login
        if not self.app.solver.is_logged_in():
            self.log("Chua dang nhap Gemini!")
            self.update_status("Can dang nhap Gemini", (1, 0.5, 0.5, 1))
            self.app.show_login_popup()
            return
        
        self.is_running = True
        self.btn_start.disabled = True
        self.btn_stop.disabled = False
        self.update_status("Dang chay...", (0.5, 1, 0.5, 1))
        self.log("Bat dau giai quiz...")
        
        # Start solver loop
        Clock.schedule_interval(self.solver_tick, 2.0)
    
    def stop_solving(self):
        """Stop the auto-solve loop"""
        self.is_running = False
        self.btn_start.disabled = False
        self.btn_stop.disabled = True
        self.update_status("Da dung", (0.8, 0.8, 0.8, 1))
        self.log("Da dung. Nhan Bat dau de tiep tuc.")
        
        Clock.unschedule(self.solver_tick)
    
    def solver_tick(self, dt):
        """Main solver loop - runs every 2 seconds"""
        if not self.is_running:
            return False
        
        helper = get_accessibility_helper()
        
        # Step 1: Find question text
        self.log("Dang tim cau hoi...")
        question = helper.find_question_text()
        
        if not question:
            self.log("Khong tim thay cau hoi. Cho...")
            return True
        
        self.log(f"Cau hoi: {question[:50]}...")
        
        # Step 2: Find answer options
        options = helper.find_answer_options()
        option_texts = [f"{letter}. {text}" for letter, text, _ in options]
        
        # Step 3: Ask Gemini
        self.log("Dang hoi Gemini...")
        self.update_status("Dang xu ly...", (1, 1, 0.5, 1))
        
        answer = self.app.solver.solve(question, option_texts)
        
        if answer:
            self.log(f"Dap an: {answer}")
            self.update_status(f"Dap an: {answer}", (0.5, 1, 0.5, 1))
            
            # Step 4: Click answer
            if helper.click_answer(answer):
                self.solved_count += 1
                self.counter_label.text = f'Da giai: {self.solved_count} cau'
                self.log(f"Da chon {answer}. Tong: {self.solved_count}")
                
                # Wait a bit then go to next
                Clock.schedule_once(lambda dt: helper.go_next_question(), 1.0)
            else:
                self.log("Khong the click dap an")
        else:
            self.log("Khong tim thay dap an tu Gemini")
            self.update_status("Loi Gemini", (1, 0.5, 0.5, 1))
        
        return True
    
    def open_settings(self, instance):
        """Open settings popup"""
        self.app.show_settings_popup()
    
    def open_accessibility(self, instance):
        """Open accessibility settings"""
        helper = get_accessibility_helper()
        helper.open_settings()
        self.log("Mo Accessibility Settings...")


class LoginPopup(Popup):
    """Popup for Gemini login with WebView option"""
    
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app = app_ref
        self.title = 'Dang nhap Gemini'
        self.size_hint = (0.9, 0.7)
        
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        # Instructions
        content.add_widget(Label(
            text='Chon cach dang nhap:',
            size_hint_y=0.15,
            font_size='16sp'
        ))
        
        # Option 1: WebView login (recommended)
        btn_webview = Button(
            text='Dang nhap qua WebView (Tu dong)',
            size_hint_y=0.2,
            background_color=(0.2, 0.7, 0.3, 1),
            font_size='16sp'
        )
        btn_webview.bind(on_press=self.open_webview_login)
        content.add_widget(btn_webview)
        
        # Separator
        content.add_widget(Label(
            text='--- hoac ---',
            size_hint_y=0.1,
            color=(0.6, 0.6, 0.6, 1)
        ))
        
        # Option 2: Manual cookie input
        content.add_widget(Label(
            text='Nhap cookie thu cong:',
            size_hint_y=0.1
        ))
        
        self.cookie_input = TextInput(
            hint_text='Paste __Secure-1PSID cookie...',
            multiline=False,
            size_hint_y=0.15
        )
        content.add_widget(self.cookie_input)
        
        # Buttons row
        buttons = BoxLayout(size_hint_y=0.15, spacing=10)
        
        btn_save = Button(
            text='Luu Cookie',
            background_color=(0.3, 0.5, 0.8, 1)
        )
        btn_save.bind(on_press=self.save_cookie)
        buttons.add_widget(btn_save)
        
        btn_cancel = Button(
            text='Huy',
            background_color=(0.5, 0.5, 0.5, 1)
        )
        btn_cancel.bind(on_press=self.dismiss)
        buttons.add_widget(btn_cancel)
        
        content.add_widget(buttons)
        
        # Status
        self.status = Label(
            text='',
            size_hint_y=0.15,
            color=(0.5, 1, 0.5, 1)
        )
        content.add_widget(self.status)
        
        self.content = content
    
    def open_webview_login(self, instance):
        """Open WebView activity for Gemini login"""
        if ANDROID:
            try:
                # Launch our GeminiLoginActivity
                GeminiLoginActivity = autoclass('org.nhat.quizsolver.GeminiLoginActivity')
                currentActivity = PythonActivity.mActivity
                intent = Intent(currentActivity, GeminiLoginActivity)
                
                # Start activity for result
                currentActivity.startActivityForResult(intent, 1001)
                
                self.status.text = "Dang mo WebView..."
                self.status.color = (0.5, 1, 0.5, 1)
                
                # Set up activity result handler
                activity.bind(on_activity_result=self._on_activity_result)
                
            except Exception as e:
                self.status.text = f"Loi: {e}"
                self.status.color = (1, 0.5, 0.5, 1)
                print(f"[Login] WebView error: {e}")
                
                # Fallback to browser
                self._open_browser()
        else:
            import webbrowser
            webbrowser.open("https://gemini.google.com/app")
            self.status.text = "Mo browser. Copy cookie sau khi dang nhap."
    
    def _on_activity_result(self, request_code, result_code, intent):
        """Handle result from WebView login activity"""
        print(f"[Login] Activity result: request={request_code}, result={result_code}")
        
        if request_code == 1001:  # Our login request
            if result_code == -1:  # RESULT_OK
                # Reload cookies from file (saved by Java activity)
                self.app.solver.cookies = self.app.solver._load_cookies()
                
                if self.app.solver.is_logged_in():
                    self.status.text = "Dang nhap thanh cong!"
                    self.status.color = (0.5, 1, 0.5, 1)
                    
                    # Close popup after short delay
                    Clock.schedule_once(lambda dt: self.dismiss(), 1.0)
                else:
                    self.status.text = "Khong tim thay cookie. Thu lai."
                    self.status.color = (1, 0.5, 0.5, 1)
            else:
                self.status.text = "Da huy dang nhap."
                self.status.color = (1, 0.5, 0.5, 1)
    
    def _open_browser(self):
        """Fallback: open in external browser"""
        try:
            currentActivity = PythonActivity.mActivity
            intent = Intent(Intent.ACTION_VIEW)
            intent.setData(Uri.parse("https://gemini.google.com/app"))
            currentActivity.startActivity(intent)
            self.status.text = "Da mo browser. Copy cookie sau."
        except Exception as e:
            self.status.text = f"Loi: {e}"
    
    def save_cookie(self, instance):
        """Save manually entered cookie"""
        cookie = self.cookie_input.text.strip()
        if not cookie:
            self.status.text = "Vui long nhap cookie!"
            self.status.color = (1, 0.5, 0.5, 1)
            return
        
        self.app.solver.set_cookie('__Secure-1PSID', cookie)
        self.status.text = "Da luu cookie!"
        self.status.color = (0.5, 1, 0.5, 1)
        
        Clock.schedule_once(lambda dt: self.dismiss(), 1.0)


class SettingsPopup(Popup):
    """Settings popup"""
    
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app = app_ref
        self.title = 'Cai dat'
        self.size_hint = (0.9, 0.5)
        
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        # Model selection
        content.add_widget(Label(text='Gemini Model:', size_hint_y=0.2))
        
        models = BoxLayout(size_hint_y=0.2, spacing=5)
        for model in ['2.5-flash', '2.5-pro']:
            btn = Button(
                text=model,
                background_color=(0.3, 0.5, 0.8, 1) if model == self.app.solver.model else (0.4, 0.4, 0.4, 1)
            )
            btn.bind(on_press=lambda x, m=model: self.select_model(m))
            models.add_widget(btn)
        content.add_widget(models)
        
        # Status
        status_text = "Da dang nhap" if self.app.solver.is_logged_in() else "Chua dang nhap"
        status_color = (0.5, 1, 0.5, 1) if self.app.solver.is_logged_in() else (1, 0.5, 0.5, 1)
        content.add_widget(Label(
            text=f'Trang thai: {status_text}',
            size_hint_y=0.2,
            color=status_color
        ))
        
        # Logout button
        if self.app.solver.is_logged_in():
            btn_logout = Button(
                text='Dang xuat',
                size_hint_y=0.2,
                background_color=(0.7, 0.3, 0.2, 1)
            )
            btn_logout.bind(on_press=self.logout)
            content.add_widget(btn_logout)
        
        # Close
        btn_close = Button(
            text='Dong',
            size_hint_y=0.2,
            background_color=(0.4, 0.4, 0.5, 1)
        )
        btn_close.bind(on_press=self.dismiss)
        content.add_widget(btn_close)
        
        self.content = content
    
    def select_model(self, model):
        """Select Gemini model"""
        self.app.solver.model = model
        self.dismiss()
    
    def logout(self, instance):
        """Logout from Gemini"""
        self.app.solver.cookies = {}
        if os.path.exists(self.app.solver.cookies_path):
            os.remove(self.app.solver.cookies_path)
        self.dismiss()


class QuizSolverApp(App):
    """Main Quiz Solver Application"""
    
    def build(self):
        # Set window properties
        Window.clearcolor = (0, 0, 0, 0)  # Transparent for overlay effect
        
        # Initialize solver
        cookies_path = 'gemini_cookies.json'
        if ANDROID:
            # Use app private directory
            cookies_path = os.path.join(
                os.environ.get('ANDROID_PRIVATE', '.'),
                'gemini_cookies.json'
            )
        self.solver = GeminiSolver(cookies_path)
        
        # Create root layout
        self.root = FloatLayout()
        
        # Create floating panel
        self.panel = FloatingPanel(self)
        self.root.add_widget(self.panel)
        
        # Request permissions on Android
        if ANDROID:
            self._request_permissions()
        
        return self.root
    
    def _request_permissions(self):
        """Request Android permissions"""
        request_permissions([
            Permission.INTERNET
        ])
        
        # Check overlay permission
        helper = get_accessibility_helper()
        if not helper.has_overlay_permission():
            helper.request_overlay_permission()
    
    def show_login_popup(self):
        """Show login popup"""
        popup = LoginPopup(self)
        popup.open()
    
    def show_settings_popup(self):
        """Show settings popup"""
        popup = SettingsPopup(self)
        popup.open()


if __name__ == '__main__':
    QuizSolverApp().run()
