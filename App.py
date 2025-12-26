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
        
        # 1. Variables por defecto
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

        # 2. Motor Lógico (Incluye DB)
        self.engine = DownloadEngine(log_callback=self.update_log_safe)
        
        # 3. CARGAR CONFIGURACIÓN PERSISTENTE
        self.load_app_settings()

        # 4. Vista
        callbacks = {
            'start': self.start_download,
            'stop': self.stop_download,
            'open_settings': self.open_settings_window,
            'select_folder': self.select_folder
        }
        self.view = MainView(root, callbacks, self.variables)

        # Guardar configuración al cerrar ventana
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_app_settings(self):
        """Carga la configuración desde la base de datos."""
        try:
            settings = self.engine.db.load_settings()
            
            if 'download_path' in settings and os.path.isdir(settings['download_path']):
                self.variables['download_path'].set(settings['download_path'])
            if 'cookie_path' in settings:
                self.variables['cookie_path'].set(settings['cookie_path'])
            if 'format' in settings:
                self.variables['format'].set(settings['format'])
            if 'bitrate' in settings:
                self.variables['bitrate'].set(settings['bitrate'])
            if 'separator' in settings:
                self.variables['separator'].set(settings['separator'])
            
            # Nota: Cargar el estado de los tags es más complejo, 
            # se podría guardar como un string JSON en la DB si se desea.
        except Exception as e:
            print(f"No se pudo cargar config: {e}")

    def save_app_settings(self):
        """Guarda el estado actual en la DB."""
        self.engine.db.save_setting('download_path', self.variables['download_path'].get())
        self.engine.db.save_setting('cookie_path', self.variables['cookie_path'].get())
        self.engine.db.save_setting('format', self.variables['format'].get())
        self.engine.db.save_setting('bitrate', self.variables['bitrate'].get())
        self.engine.db.save_setting('separator', self.variables['separator'].get())

    def on_close(self):
        self.save_app_settings()
        self.root.destroy()

    def select_folder(self):
        d = filedialog.askdirectory()
        if d: 
            self.variables['download_path'].set(d)
            self.save_app_settings() # Guardar inmediatamente al cambiar

    def open_settings_window(self):
        SettingsView(self.root, self.variables, self.tags_data)
        # Podrías agregar un callback al SettingsView para guardar al cerrar el modal

    def start_download(self):
        # Guardamos configuración al iniciar descarga también
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