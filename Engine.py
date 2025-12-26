import yt_dlp
from yt_dlp.utils import DownloadError
import os
import time
import random
from Logger import ConsoleLogger
from Database import DatabaseManager

class DownloadEngine:
    def __init__(self, log_callback):
        self.log = log_callback
        self.stop_flag = False
        self.db = DatabaseManager()
        self.is_paused_by_limit = False

    def request_stop(self):
        self.stop_flag = True
        self.is_paused_by_limit = False 

    def run(self, url, path, config):
        self.stop_flag = False
        cookie = config.get('cookie_path')
        name_template = config.get('name_template', '%(title)s')
        
        # 1. Extracción (Flat)
        ydl_opts_list = { 'extract_flat': True, 'quiet': True, 'ignoreerrors': True }
        if cookie: ydl_opts_list['cookiefile'] = cookie

        playlist_id = None
        
        try:
            self.log("--- SINCRONIZANDO CON BASE DE DATOS... ---")
            with yt_dlp.YoutubeDL(ydl_opts_list) as ydl:
                info = ydl.extract_info(url, download=False)
                pl_title = info.get('title', 'Lista Sin Titulo')
                playlist_id = self.db.get_or_create_playlist(url, pl_title)
                
                entries = info.get('entries', [info]) if 'entries' in info else [info]
                added = self.db.add_videos_to_playlist(playlist_id, list(entries))
                self.log(f"Nuevos videos en cola: {added}")

        except Exception as e:
            self.log(f"Error al analizar URL: {e}")
            return

        # 2. Descarga
        pending_videos = self.db.get_pending_videos(playlist_id)
        total_pending = len(pending_videos)
        
        if total_pending == 0:
            self.log("¡Todos los videos registrados están marcados como completados!")
            return

        self.log(f"--- PROCESANDO {total_pending} VIDEOS PENDIENTES ---")

        # pending_videos ahora trae: (db_id, title, url, video_id, filepath_antiguo)
        for i, (db_id, title, video_url, vid_id, old_path) in enumerate(pending_videos):
            if self.stop_flag:
                self.log("⛔ DETENIDO POR USUARIO.")
                break

            # --- VERIFICACIÓN DE ARCHIVO EXISTENTE (Lógica Anti-Duplicados) ---
            # A veces la DB dice PENDING pero el archivo ya está ahí (crash anterior, etc.)
            # Intentamos adivinar si existe buscando el ID en la carpeta
            already_downloaded = False
            for f_name in os.listdir(path):
                # Si el ID del video está en el nombre del archivo y es de audio
                if vid_id in f_name and any(f_name.endswith(ext) for ext in ['.mp3', '.m4a', '.wav', '.flac']):
                    full_path = os.path.join(path, f_name)
                    self.log(f"✨ El archivo ya existe: {f_name}. Marcando como completado.")
                    self.db.update_video_status(db_id, "COMPLETED", filepath=full_path)
                    already_downloaded = True
                    break
            
            if already_downloaded:
                continue

            # --- MANEJO DE RATE LIMIT ---
            while self.is_paused_by_limit:
                if self.stop_flag: break
                self.log("⏳ Pausa por Rate Limit...")
                for _ in range(60): 
                    if self.stop_flag: break
                    time.sleep(1)
                self.is_paused_by_limit = False 

            self.log(f"\n[{i+1}/{total_pending}] Descargando: {title}")

            # Variable para capturar el nombre final del archivo
            final_filename = [None] 

            def progress_hook(d):
                if d['status'] == 'finished':
                    final_filename[0] = d.get('filename')

            ydl_opts_down = {
                'format': 'bestaudio/best',
                # Agregamos el ID al nombre para facilitar la detección futura de duplicados
                'outtmpl': os.path.join(path, f'{name_template} [%(id)s].%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio', 
                    'preferredcodec': config.get('format'), 
                    'preferredquality': config.get('bitrate')
                }, {'key': 'FFmpegMetadata', 'add_metadata': True}],
                'quiet': True, 'no_warnings': True,
                'logger': ConsoleLogger(self.log),
                'progress_hooks': [progress_hook] # Hook para capturar nombre
            }
            if cookie: ydl_opts_down['cookiefile'] = cookie

            # Intentos
            max_retries = 3
            attempt = 0
            
            while attempt < max_retries:
                if self.stop_flag: break
                attempt += 1
                
                status, err_msg = self._download_safe(ydl_opts_down, video_url)
                
                if status == "OK":
                    # Si yt-dlp convirtió el archivo (ej. webm -> mp3), el filename del hook
                    # podría tener la extensión vieja. Ajustamos la extensión:
                    saved_path = final_filename[0] if final_filename[0] else "Unknown"
                    target_ext = config.get('format')
                    if saved_path != "Unknown":
                        base, _ = os.path.splitext(saved_path)
                        # Predecimos el nombre final post-conversión
                        saved_path = f"{base}.{target_ext}"

                    self.db.update_video_status(db_id, "COMPLETED", filepath=saved_path)
                    break 
                
                elif status == "RATE_LIMIT":
                    self.log("⚠️ BLOQUEO DE YOUTUBE DETECTADO (429).")
                    self.is_paused_by_limit = True
                    self._wait_cooldown(minutes=5)
                    break 

                else:
                    if attempt < max_retries:
                        self.log(f"⚠️ Reintentando ({attempt}/{max_retries})...")
                        time.sleep(5)
                    else:
                        self.log(f"❌ Error final: {err_msg}")
                        self.db.update_video_status(db_id, "ERROR", error_msg=err_msg)
            
            time.sleep(random.uniform(2, 5))

        self.log("\n--- TAREA FINALIZADA ---")

    def _download_safe(self, opts, url):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
                return "OK", ""
        except DownloadError as e:
            msg = str(e)
            if "HTTP Error 429" in msg or "rate-limited" in msg:
                return "RATE_LIMIT", msg
            return "ERROR", msg
        except Exception as e:
            return "CRITICAL", str(e)

    def _wait_cooldown(self, minutes):
        seconds = minutes * 60
        for s in range(seconds):
            if self.stop_flag: return
            if s % 60 == 0:
                self.log(f"⏳ Enfriando... {minutes - (s // 60)} min restantes.")
            time.sleep(1)