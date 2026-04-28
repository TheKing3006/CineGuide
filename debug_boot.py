import traceback
import sys
import os

try:
    print("Attempting to import cineguide...")
    import customtkinter as ctk
    from cineguide import CineGuideApp
    import tkinter as tk
    
    print("Attempting to initialize App...")
    root = ctk.CTk()
    app = CineGuideApp(root)
    print("App Init OK")
    
except Exception:
    traceback.print_exc()
    sys.exit(1)
