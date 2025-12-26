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
        
        # 1. Extracción (Flat) para llenar la DB
        ydl_opts_list = { 'extract_flat': True, 'quiet': True, 'ignoreerrors': True }
        if cookie: ydl_opts_list['cookiefile'] = cookie

        playlist_id = None
        
        try:
            self.log("--- SINCRONIZANDO LISTA... ---")
            with yt_dlp.YoutubeDL(ydl_opts_list) as ydl:
                info = ydl.extract_info(url, download=False)
                pl_title = info.get('title', 'Lista Sin Titulo')
                playlist_id = self.db.get_or_create_playlist(url, pl_title)
                
                entries = info.get('entries', [info]) if 'entries' in info else [info]
                added = self.db.add_videos_to_playlist(playlist_id, list(entries))
                self.log(f"Videos nuevos detectados: {added}")

        except Exception as e:
            self.log(f"Error al analizar URL: {e}")
            return

        # 2. Bucle de Descarga Inteligente
        pending_videos = self.db.get_pending_videos(playlist_id)
        total_pending = len(pending_videos)
        
        if total_pending == 0:
            self.log("¡Todo está al día!")
            return

        self.log(f"--- PROCESANDO {total_pending} VIDEOS ---")

        # pending_videos trae: (db_id, title, url, video_id)
        for i, (db_id, title, video_url, vid_id) in enumerate(pending_videos):
            if self.stop_flag:
                self.log("⛔ DETENIDO POR EL USUARIO.")
                break

            # --- LÓGICA ANTI-DUPLICADOS (CRÍTICO) ---
            # Verificamos si el archivo YA existe físicamente en la carpeta
            file_exists = False
            found_file = ""
            
            # Buscamos archivos que contengan el ID del video y sean de audio
            if os.path.exists(path):
                for f_name in os.listdir(path):
                    if vid_id in f_name and any(f_name.endswith(ext) for ext in ['.mp3', '.m4a', '.wav', '.flac', '.ogg']):
                        file_exists = True
                        found_file = os.path.join(path, f_name)
                        break
            
            if file_exists:
                self.log(f"✅ Omitiendo (Ya existe): {title}")
                # Actualizamos la DB para que no vuelva a preguntar
                self.db.update_video_status(db_id, "COMPLETED", filepath=found_file)
                continue

            # --- GESTIÓN DE PAUSA (RATE LIMIT) ---
            while self.is_paused_by_limit:
                if self.stop_flag: break
                self.log("⏳ Pausa por bloqueo de IP...")
                for _ in range(60): 
                    if self.stop_flag: break
                    time.sleep(1)
                self.is_paused_by_limit = False 

            self.log(f"\n[{i+1}/{total_pending}] Descargando: {title}")

            # Hook para capturar el nombre real del archivo generado
            final_filename = [None] 
            def progress_hook(d):
                if d['status'] == 'finished':
                    final_filename[0] = d.get('filename')

            # Agregamos el ID al nombre para garantizar unicidad y detección futura
            # Esto soluciona que 'title' cambie y no encontremos el archivo
            out_tmpl = os.path.join(path, f'{name_template} [%(id)s].%(ext)s')

            ydl_opts_down = {
                'format': 'bestaudio/best',
                'outtmpl': out_tmpl,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio', 
                    'preferredcodec': config.get('format'), 
                    'preferredquality': config.get('bitrate')
                }, {'key': 'FFmpegMetadata', 'add_metadata': True}],
                'quiet': True, 'no_warnings': True,
                'logger': ConsoleLogger(self.log),
                'progress_hooks': [progress_hook]
            }
            if cookie: ydl_opts_down['cookiefile'] = cookie

            # --- REINTENTOS ---
            max_retries = 3
            attempt = 0
            
            while attempt < max_retries:
                if self.stop_flag: break
                attempt += 1
                
                status, err_msg = self._download_safe(ydl_opts_down, video_url)
                
                if status == "OK":
                    # Intentamos deducir el nombre final
                    saved_path = final_filename[0] if final_filename[0] else "Unknown"
                    # Ajuste de extensión si hubo conversión
                    target_ext = config.get('format')
                    if saved_path != "Unknown" and not saved_path.endswith(target_ext):
                        base, _ = os.path.splitext(saved_path)
                        saved_path = f"{base}.{target_ext}"

                    self.db.update_video_status(db_id, "COMPLETED", filepath=saved_path)
                    break 
                
                elif status == "RATE_LIMIT":
                    self.log("⚠️ BLOQUEO DE YOUTUBE (429). Iniciando espera larga.")
                    self.is_paused_by_limit = True
                    self._wait_cooldown(minutes=5)
                    # Rompemos el ciclo de reintentos de ESTE video para pausar antes del siguiente
                    break 

                else:
                    if attempt < max_retries:
                        self.log(f"⚠️ Fallo intento {attempt}. Reintentando en 5s...")
                        time.sleep(5)
                    else:
                        self.log(f"❌ Error persistente: {err_msg}")
                        # Marcamos como ERROR para que se pueda reintentar en el futuro
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
                self.log(f"⏳ Enfriando motor... {minutes - (s // 60)} min restantes.")
            time.sleep(1)