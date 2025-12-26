import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

class SettingsView:
    """Maneja la ventana modal de configuración."""
    def __init__(self, parent, context_vars, tags_data):
        self.top = tk.Toplevel(parent)
        self.top.title("Configuración Avanzada")
        self.top.geometry("600x550")
        self.top.grab_set()
        
        self.vars = context_vars # Diccionario con las variables Tkinter
        self.tags_data = tags_data
        
        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self.top)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Pestaña 1
        tab_names = ttk.Frame(notebook, padding=10)
        notebook.add(tab_names, text="Formato y Nombres")
        self._build_audio_frame(tab_names)
        self._build_tags_frame(tab_names)

        # Pestaña 2
        tab_sec = ttk.Frame(notebook, padding=10)
        notebook.add(tab_sec, text="Cookies")
        self._build_cookie_frame(tab_sec)

        ttk.Button(self.top, text="Guardar y Cerrar", command=self.top.destroy).pack(pady=10)

    def _build_audio_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Calidad de Audio", padding=10)
        frame.pack(fill="x", pady=5)
        ttk.Label(frame, text="Formato:").pack(side="left")
        ttk.Combobox(frame, textvariable=self.vars['format'], values=["mp3", "m4a", "wav"], width=6).pack(side="left", padx=5)
        ttk.Label(frame, text="Bitrate:").pack(side="left", padx=10)
        ttk.Combobox(frame, textvariable=self.vars['bitrate'], values=["128", "192", "320"], width=6).pack(side="left")

    def _build_tags_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Constructor de Nombres", padding=10)
        frame.pack(fill="both", expand=True, pady=10)
        
        self.list_frame = ttk.Frame(frame)
        self.list_frame.pack(fill="x", pady=5)
        self.render_tag_list()

        sep_cont = ttk.Frame(frame)
        sep_cont.pack(fill="x", pady=10)
        ttk.Label(sep_cont, text="Separador:").pack(side="left")
        ttk.Entry(sep_cont, textvariable=self.vars['separator'], width=5).pack(side="left")

    def _build_cookie_frame(self, parent):
        ttk.Label(parent, text="Ruta cookies.txt:").pack(anchor="w")
        cont = ttk.Frame(parent)
        cont.pack(fill="x")
        ttk.Entry(cont, textvariable=self.vars['cookie_path']).pack(side="left", fill="x", expand=True)
        ttk.Button(cont, text="Buscar...", command=self._browse_cookie).pack(side="left")

    def _browse_cookie(self):
        f = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if f: self.vars['cookie_path'].set(f)

    def render_tag_list(self):
        for widget in self.list_frame.winfo_children(): widget.destroy()
        
        for i, item in enumerate(self.tags_data):
            row = ttk.Frame(self.list_frame)
            row.pack(fill="x", pady=2)
            ttk.Checkbutton(row, text=item["label"], variable=item["active"], width=12).pack(side="left")
            
            # Botones de movimiento
            if i > 0: ttk.Button(row, text="↑", width=2, command=lambda x=i: self._move_tag(x, -1)).pack(side="left")
            else: ttk.Label(row, width=4).pack(side="left") # Spacer
            
            if i < len(self.tags_data) - 1: ttk.Button(row, text="↓", width=2, command=lambda x=i: self._move_tag(x, 1)).pack(side="left")
            
            ttk.Label(row, text=item["code"], foreground="gray").pack(side="left", padx=10)

    def _move_tag(self, index, direction):
        new_index = index + direction
        if 0 <= new_index < len(self.tags_data):
            self.tags_data[index], self.tags_data[new_index] = self.tags_data[new_index], self.tags_data[index]
            self.render_tag_list()