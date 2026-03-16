#!/usr/bin/env python
"""Quick test to see the error"""

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    import threading
    import json
    import os
    import time
    import random
    import requests
    from datetime import datetime
    from pathlib import Path
    import sys
    from hashlib import md5
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    import undetected_chromedriver as uc
    import google.generativeai as genai
    
    print("✅ All imports successful")
    
    # Try to create app
    from quiz_solver_multi import MultiAccountApp
    print("✅ Class import successful")
    
    # Create root window
    root = tk.Tk()
    app = MultiAccountApp(root)
    print("✅ App created successfully")
    
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
