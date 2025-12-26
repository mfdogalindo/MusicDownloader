import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import yt_dlp
import threading
import os
import time
import random
import csv
import datetime

class ConsoleLogger:
    """Manejador de logs que conecta yt-dlp con la UI mediante un callback."""
    def __init__(self, callback):
        self.callback = callback

    def debug(self, msg): pass 

    def info(self, msg):
        if "[download]" in msg and "Hz" in msg: return 
        self.callback(msg)

    def warning(self, msg):
        self.callback(f"⚠️ ADVERTENCIA: {msg}")

    def error(self, msg):
        self.callback(f"❌ ERROR INTERNO: {msg}")