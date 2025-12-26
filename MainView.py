import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

class MainView:
    """Interfaz Gráfica Principal."""
    def __init__(self, root, callbacks, context_vars):
        self.root = root
        self.cb = callbacks # Diccionario de funciones (start, stop, settings, folder)
        self.vars = context_vars
        self._setup_window()
        self._build_components()

    def _setup_window(self):
        self.root.title("YouTube Downloader V6 - Modular")
        self.root.geometry("800x650")

    def _build_components(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill="both", expand=True)

        # Header
        top = ttk.Frame(main_frame)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="Gestor de Descargas Modular", font=("Arial", 12, "bold")).pack(side="left")
        ttk.Button(top, text="⚙️ Configuración", command=self.cb['open_settings']).pack(side="right")

        # URL
        url_frame = ttk.LabelFrame(main_frame, text="URL del Video/Playlist", padding="10")
        url_frame.pack(fill="x", pady=5)
        ttk.Entry(url_frame, textvariable=self.vars['url']).pack(fill="x")

        # Path
        dest_frame = ttk.Frame(main_frame)
        dest_frame.pack(fill="x", pady=5)
        ttk.Label(dest_frame, text="Guardar en:").pack(side="left")
        ttk.Entry(dest_frame, textvariable=self.vars['download_path'], state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(dest_frame, text="📂", width=3, command=self.cb['select_folder']).pack(side="left")

        # Botones
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=15)
        self.btn_start = tk.Button(btn_frame, text="▶ INICIAR", bg="#28a745", fg="white", 
                                   command=self.cb['start'], height=2)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_stop = tk.Button(btn_frame, text="⏹ DETENER", bg="#dc3545", fg="white", 
                                  state="disabled", command=self.cb['stop'], height=2)
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=(5, 0))

        # Log
        self.log_area = scrolledtext.ScrolledText(main_frame, height=15, state='disabled', bg="#1e1e1e", fg="#00ff00")
        self.log_area.pack(fill="both", expand=True)

    def append_log(self, msg):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"{msg}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def toggle_controls(self, is_running):
        state_start = "disabled" if is_running else "normal"
        state_stop = "normal" if is_running else "disabled"
        self.btn_start.config(state=state_start)
        self.btn_stop.config(state=state_stop)