"""
Accessibility Service Bridge - accessibility.py
=================================================
Python wrapper để gọi Java AccessibilityService
"""

from kivy.utils import platform

if platform == 'android':
    from jnius import autoclass, cast, PythonJavaClass, java_method
    from android import activity
    
    # Android classes
    Context = autoclass('android.content.Context')
    Settings = autoclass('android.provider.Settings')
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    
    # Our accessibility service
    try:
        QuizAccessibilityService = autoclass('org.nhat.quizsolver.QuizAccessibilityService')
        HAS_SERVICE = True
    except Exception as e:
        print(f"[Accessibility] Could not load QuizAccessibilityService: {e}")
        QuizAccessibilityService = None
        HAS_SERVICE = False
    
    ANDROID = True
else:
    ANDROID = False
    HAS_SERVICE = False
    print("[Accessibility] Desktop mode - using mock service")


class QuizCallback:
    """Callback interface for quiz events (for desktop testing)"""
    def on_question_found(self, question, options):
        pass
    
    def on_answer_clicked(self, letter):
        pass
    
    def on_error(self, message):
        pass


class AccessibilityHelper:
    """
    Helper class for Accessibility Service operations
    Bridges Python to Java AccessibilityService
    """
    
    def __init__(self):
        self._enabled = False
        self._callback = None
        self._last_question = ""
        self._last_options = []
        
        if ANDROID:
            self._check_enabled()
    
    def _check_enabled(self):
        """Check if accessibility service is enabled"""
        if not ANDROID:
            self._enabled = True
            return
        
        try:
            context = PythonActivity.mActivity
            enabled_services = Settings.Secure.getString(
                context.getContentResolver(),
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            )
            
            service_name = "org.nhat.quizsolver/org.nhat.quizsolver.QuizAccessibilityService"
            self._enabled = service_name in (enabled_services or '')
            
            print(f"[Accessibility] Service enabled: {self._enabled}")
        except Exception as e:
            print(f"[Accessibility] Check error: {e}")
            self._enabled = False
    
    def is_enabled(self):
        """Check if accessibility is enabled"""
        if ANDROID:
            self._check_enabled()
        return self._enabled
    
    def get_service(self):
        """Get the Java service instance"""
        if not ANDROID or not HAS_SERVICE:
            return None
        
        try:
            return QuizAccessibilityService.getInstance()
        except Exception as e:
            print(f"[Accessibility] Get service error: {e}")
            return None
    
    def open_settings(self):
        """Open accessibility settings page"""
        if not ANDROID:
            print("[Accessibility] Not on Android")
            return
        
        try:
            context = PythonActivity.mActivity
            intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            context.startActivity(intent)
            print("[Accessibility] Opened accessibility settings")
        except Exception as e:
            print(f"[Accessibility] Open settings error: {e}")
    
    def request_overlay_permission(self):
        """Request permission to draw over other apps"""
        if not ANDROID:
            return True
        
        try:
            context = PythonActivity.mActivity
            
            if Settings.canDrawOverlays(context):
                print("[Accessibility] Overlay permission already granted")
                return True
            
            intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse(f"package:{context.getPackageName()}")
            )
            context.startActivity(intent)
            print("[Accessibility] Requested overlay permission")
            return False
        except Exception as e:
            print(f"[Accessibility] Overlay permission error: {e}")
            return False
    
    def has_overlay_permission(self):
        """Check if overlay permission is granted"""
        if not ANDROID:
            return True
        
        try:
            context = PythonActivity.mActivity
            return Settings.canDrawOverlays(context)
        except Exception as e:
            print(f"[Accessibility] Check overlay error: {e}")
            return False
    
    def scan_for_content(self):
        """Trigger a scan for quiz content"""
        service = self.get_service()
        if service:
            try:
                service.rescan()
                return True
            except Exception as e:
                print(f"[Accessibility] Scan error: {e}")
        return False
    
    def find_question_text(self):
        """
        Get the current question text from the screen
        
        Returns:
            str: Question text or None
        """
        service = self.get_service()
        if service:
            try:
                question = service.getLastQuestion()
                if question:
                    return str(question)
            except Exception as e:
                print(f"[Accessibility] Get question error: {e}")
        
        return self._last_question or None
    
    def find_answer_options(self):
        """
        Get answer options from the screen
        
        Returns:
            list: List of tuples (letter, text, bounds_dict)
        """
        service = self.get_service()
        if service:
            try:
                java_options = service.getLastOptions()
                options = []
                
                for i in range(java_options.size()):
                    opt = java_options.get(i)
                    letter = str(opt.letter)
                    text = str(opt.text)
                    bounds = opt.bounds
                    bounds_dict = {
                        'left': bounds.left,
                        'top': bounds.top,
                        'right': bounds.right,
                        'bottom': bounds.bottom
                    }
                    options.append((letter, text, bounds_dict))
                
                self._last_options = options
                return options
            except Exception as e:
                print(f"[Accessibility] Get options error: {e}")
        
        return self._last_options
    
    def click_answer(self, letter):
        """
        Click on an answer option by letter
        
        Args:
            letter: 'A', 'B', 'C', or 'D'
            
        Returns:
            bool: True if clicked successfully
        """
        service = self.get_service()
        if service:
            try:
                result = service.clickAnswer(letter.upper())
                print(f"[Accessibility] Click answer {letter}: {result}")
                return bool(result)
            except Exception as e:
                print(f"[Accessibility] Click answer error: {e}")
        
        return False
    
    def click_at(self, x, y):
        """
        Perform click at specific coordinates
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            bool: True if clicked successfully
        """
        service = self.get_service()
        if service:
            try:
                result = service.clickAt(int(x), int(y))
                print(f"[Accessibility] Click at ({x}, {y}): {result}")
                return bool(result)
            except Exception as e:
                print(f"[Accessibility] Click at error: {e}")
        
        return False
    
    def go_next_question(self):
        """Navigate to next question"""
        service = self.get_service()
        if service:
            try:
                service.goNextQuestion()
                print("[Accessibility] Going to next question")
                return True
            except Exception as e:
                print(f"[Accessibility] Go next error: {e}")
        
        return False
    
    def swipe(self, start_x, start_y, end_x, end_y, duration_ms=300):
        """
        Perform swipe gesture
        
        Args:
            start_x, start_y: Starting point
            end_x, end_y: Ending point
            duration_ms: Swipe duration in milliseconds
            
        Returns:
            bool: True if swiped successfully
        """
        service = self.get_service()
        if service:
            try:
                result = service.swipe(
                    int(start_x), int(start_y),
                    int(end_x), int(end_y),
                    int(duration_ms)
                )
                return bool(result)
            except Exception as e:
                print(f"[Accessibility] Swipe error: {e}")
        
        return False


# Singleton instance
_accessibility_helper = None


def get_accessibility_helper():
    """Get singleton AccessibilityHelper instance"""
    global _accessibility_helper
    if _accessibility_helper is None:
        _accessibility_helper = AccessibilityHelper()
    return _accessibility_helper
