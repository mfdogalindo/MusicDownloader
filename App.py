import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import os

from Engine import DownloadEngine  
from MainView import MainView
from SettingsView import SettingsView 

class AppController:
    def __init__(self, root):
        self.root = root
        
        # 1. Estado de la Aplicación (Variables)
        self.variables = {
            'url': tk.StringVar(),
            'download_path': tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads")),
            'cookie_path': tk.StringVar(),
            'format': tk.StringVar(value="mp3"),
            'bitrate': tk.StringVar(value="192"),
            'separator': tk.StringVar(value=" - ")
        }
        
        # Datos para nombres (Lista compleja)
        self.tags_data = [
            {"label": "Artista", "code": "%(artist)s", "active": tk.BooleanVar(value=True)},
            {"label": "Título", "code": "%(title)s",  "active": tk.BooleanVar(value=True)},
            {"label": "Álbum",   "code": "%(album)s",  "active": tk.BooleanVar(value=False)},
            {"label": "Fecha",   "code": "%(upload_date)s", "active": tk.BooleanVar(value=False)},
            {"label": "ID Video","code": "%(id)s",     "active": tk.BooleanVar(value=False)},
        ]

        # 2. Inicializar Motor Lógico
        self.engine = DownloadEngine(log_callback=self.update_log_safe)

        # 3. Inicializar Vista Principal
        callbacks = {
            'start': self.start_download,
            'stop': self.stop_download,
            'open_settings': self.open_settings_window,
            'select_folder': self.select_folder
        }
        self.view = MainView(root, callbacks, self.variables)

    # --- Acciones ---
    def select_folder(self):
        d = filedialog.askdirectory()
        if d: self.variables['download_path'].set(d)

    def open_settings_window(self):
        SettingsView(self.root, self.variables, self.tags_data)

    def start_download(self):
        url = self.variables['url'].get().strip()
        if not url:
            messagebox.showwarning("Error", "Ingrese una URL válida")
            return

        # Preparar Configuración para el motor
        # Construimos el template aquí para no ensuciar el motor con lógica de UI
        active_tags = [t["code"] for t in self.tags_data if t["active"].get()]
        if not active_tags: active_tags = ["%(title)s"]
        template = self.variables['separator'].get().join(active_tags)

        config = {
            'cookie_path': self.variables['cookie_path'].get(),
            'format': self.variables['format'].get(),
            'bitrate': self.variables['bitrate'].get(),
            'name_template': template
        }

        # Bloquear UI
        self.view.toggle_controls(is_running=True)
        
        # Lanzar Hilo
        threading.Thread(target=self._run_thread, args=(url, config)).start()

    def _run_thread(self, url, config):
        path = self.variables['download_path'].get()
        self.engine.run(url, path, config)
        
        # Al finalizar
        self.root.after(0, lambda: self.view.toggle_controls(is_running=False))
        self.root.after(0, lambda: messagebox.showinfo("Fin", "Proceso terminado"))

    def stop_download(self):
        self.engine.request_stop()
        self.update_log_safe("!!! SOLICITANDO PARADA... !!!")

    def update_log_safe(self, msg):
        # Asegurar que se ejecuta en el hilo principal de GUI
        self.root.after(0, lambda: self.view.append_log(msg))

if __name__ == "__main__":
    root = tk.Tk()
    app = AppController(root)
    root.mainloop()