import yt_dlp
import os
import time
import random
import csv
import datetime

# IMPORTAMOS NUESTRA CLASE DE UTILIDAD
from Logger import ConsoleLogger


class DownloadEngine:
    """Encargada puramente de la lógica de descarga con yt-dlp."""
    
    def __init__(self, log_callback):
        self.log = log_callback
        self.stop_flag = False

    def request_stop(self):
        self.stop_flag = True

    def run(self, url, path, config):
        """
        config: Diccionario con llaves: 
        'cookie_path', 'format', 'bitrate', 'name_template'
        """
        self.stop_flag = False
        cookie = config.get('cookie_path')
        name_template = config.get('name_template', '%(title)s')
        
        # Opciones para extraer información (rápido)
        ydl_opts_list = {
            'extract_flat': True, 'quiet': True, 'ignoreerrors': True,
        }
        if cookie: ydl_opts_list['cookiefile'] = cookie

        entries = []
        try:
            self.log("--- ANALIZANDO ENLACE... ---")
            with yt_dlp.YoutubeDL(ydl_opts_list) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    entries = list(info['entries'])
                    self.log(f"Playlist detectada: {len(entries)} elementos.")
                else:
                    entries = [info]
                    self.log("Video único detectado.")
        except Exception as e:
            self.log(f"Error de análisis: {e}")
            return

        # Preparar CSV
        csv_file = os.path.join(path, f"reporte_{int(time.time())}.csv")
        self._init_csv(csv_file)

        # Bucle de descarga
        for i, entry in enumerate(entries):
            if self.stop_flag:
                self.log("⛔ PROCESO DETENIDO POR EL USUARIO.")
                break

            if not entry: continue
            title = entry.get('title', 'Desconocido')
            
            # Filtro básico
            if "[Deleted video]" in title or "[Private video]" in title:
                self.log(f"Skipping: {title}")
                continue

            video_url = entry.get('url') or entry.get('webpage_url')
            if not video_url and entry.get('id'):
                video_url = f"https://www.youtube.com/watch?v={entry.get('id')}"

            self.log(f"\n[{i+1}/{len(entries)}] Procesando: {title}")

            # Configuración específica de descarga
            ydl_opts_down = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(path, f'{name_template}.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio', 
                    'preferredcodec': config.get('format'), 
                    'preferredquality': config.get('bitrate')
                }, {'key': 'FFmpegMetadata', 'add_metadata': True}],
                'quiet': True, 'no_warnings': True, 'ignoreerrors': True,
                'logger': ConsoleLogger(self.log),
            }
            if cookie: ydl_opts_down['cookiefile'] = cookie

            status, err_msg = self._download_single(ydl_opts_down, video_url)
            self._write_csv(csv_file, status, title, video_url, err_msg)
            
            # Pausa humana
            time.sleep(random.uniform(1.5, 4))

        self.log("\n--- TAREA FINALIZADA ---")

    def _download_single(self, opts, url):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                code = ydl.download([url])
                if code == 0: return "OK", ""
                return "ERROR_DL", "Código de salida no cero"
        except Exception as e:
            return "CRITICAL", str(e)

    def _init_csv(self, filename):
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(["Fecha", "Estado", "Titulo", "URL", "Error"])

    def _write_csv(self, filename, status, title, url, error):
        try:
            with open(filename, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow([datetime.datetime.now(), status, title, url, error])
        except: pass