#!/usr/bin/env python
"""Test runner with error capture"""

try:
    import tkinter as tk
    from quiz_solver_multi import MultiAccountApp
    
    print("🚀 Launching Quiz Solver Multi-Account Advanced...")
    root = tk.Tk()
    app = MultiAccountApp(root)
    
    # Schedule exit after 3 seconds for testing
    root.after(3000, root.quit)
    
    print("✅ App initialized, running mainloop...")
    root.mainloop()
    print("✅ mainloop completed")
    
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    
    # Keep window open to see error
    import time
    time.sleep(5)
