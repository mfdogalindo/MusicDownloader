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
        
        # 1. Variables
        self.variables = {
            'url': tk.StringVar(),
            'download_path': tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads")),
            'cookie_path': tk.StringVar(),
            'format': tk.StringVar(value="mp3"),
            'bitrate': tk.StringVar(value="192"),
            'separator': tk.StringVar(value=" - ")
        }
        
        self.tags_data = [
            {"label": "Artista", "code": "%(artist)s", "active": tk.BooleanVar(value=True)},
            {"label": "Título", "code": "%(title)s",  "active": tk.BooleanVar(value=True)},
            {"label": "Álbum",   "code": "%(album)s",  "active": tk.BooleanVar(value=False)},
            {"label": "Fecha",   "code": "%(upload_date)s", "active": tk.BooleanVar(value=False)},
            {"label": "ID Video","code": "%(id)s",     "active": tk.BooleanVar(value=False)},
        ]

        # 2. Inicializar Motor (y DB)
        self.engine = DownloadEngine(log_callback=self.update_log_safe)
        
        # 3. CARGAR CONFIGURACIÓN GUARDADA
        self.load_app_settings()

        # 4. Vista
        callbacks = {
            'start': self.start_download,
            'stop': self.stop_download,
            'open_settings': self.open_settings_window,
            'select_folder': self.select_folder
        }
        self.view = MainView(root, callbacks, self.variables)

        # Guardar al cerrar la ventana con la X
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_app_settings(self):
        """Recupera la última configuración de la DB."""
        try:
            settings = self.engine.db.load_settings()
            
            if 'download_path' in settings and os.path.exists(settings['download_path']):
                self.variables['download_path'].set(settings['download_path'])
            
            if 'cookie_path' in settings and os.path.exists(settings['cookie_path']):
                self.variables['cookie_path'].set(settings['cookie_path'])
            
            if 'format' in settings: self.variables['format'].set(settings['format'])
            if 'bitrate' in settings: self.variables['bitrate'].set(settings['bitrate'])
            if 'separator' in settings: self.variables['separator'].set(settings['separator'])
            
        except Exception as e:
            print(f"Error cargando settings: {e}")

    def save_app_settings(self):
        """Guarda el estado actual en la DB."""
        db = self.engine.db
        db.save_setting('download_path', self.variables['download_path'].get())
        db.save_setting('cookie_path', self.variables['cookie_path'].get())
        db.save_setting('format', self.variables['format'].get())
        db.save_setting('bitrate', self.variables['bitrate'].get())
        db.save_setting('separator', self.variables['separator'].get())

    def on_close(self):
        self.save_app_settings()
        self.root.destroy()

    def select_folder(self):
        d = filedialog.askdirectory()
        if d: 
            self.variables['download_path'].set(d)
            self.save_app_settings() # Guardado inmediato

    def open_settings_window(self):
        # Al abrir ajustes, pasamos las variables referenciadas.
        # Podrías agregar un callback para guardar al cerrar la ventana modal si quisieras.
        SettingsView(self.root, self.variables, self.tags_data)

    def start_download(self):
        # Guardamos la configuración antes de empezar por seguridad
        self.save_app_settings()

        url = self.variables['url'].get().strip()
        if not url:
            messagebox.showwarning("Error", "Ingrese una URL válida")
            return

        active_tags = [t["code"] for t in self.tags_data if t["active"].get()]
        if not active_tags: active_tags = ["%(title)s"]
        template = self.variables['separator'].get().join(active_tags)

        config = {
            'cookie_path': self.variables['cookie_path'].get(),
            'format': self.variables['format'].get(),
            'bitrate': self.variables['bitrate'].get(),
            'name_template': template
        }

        self.view.toggle_controls(is_running=True)
        threading.Thread(target=self._run_thread, args=(url, config)).start()

    def _run_thread(self, url, config):
        path = self.variables['download_path'].get()
        self.engine.run(url, path, config)
        self.root.after(0, lambda: self.view.toggle_controls(is_running=False))
        self.root.after(0, lambda: messagebox.showinfo("Fin", "Proceso terminado"))

    def stop_download(self):
        self.engine.request_stop()
        self.update_log_safe("!!! SOLICITANDO PARADA... !!!")

    def update_log_safe(self, msg):
        self.root.after(0, lambda: self.view.append_log(msg))

if __name__ == "__main__":
    root = tk.Tk()
    app = AppController(root)
    root.mainloop()