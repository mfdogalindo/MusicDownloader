import yt_dlp
from yt_dlp.utils import DownloadError
import os
import time
import random
import datetime
from Logger import ConsoleLogger

# Importar el nuevo gestor de DB
from Database import DatabaseManager

class DownloadEngine:
    def __init__(self, log_callback):
        self.log = log_callback
        self.stop_flag = False
        self.db = DatabaseManager() # Inicializamos la DB
        self.is_paused_by_limit = False

    def request_stop(self):
        self.stop_flag = True
        # Si estaba en espera por rate limit, esto ayudará a salir del bucle de espera
        self.is_paused_by_limit = False 

    def run(self, url, path, config):
        self.stop_flag = False
        cookie = config.get('cookie_path')
        name_template = config.get('name_template', '%(title)s')
        
        # 1. Extracción PRELIMINAR (Flat) para llenar la DB
        ydl_opts_list = {
            'extract_flat': True, 'quiet': True, 'ignoreerrors': True,
        }
        if cookie: ydl_opts_list['cookiefile'] = cookie

        playlist_id = None
        
        try:
            self.log("--- SINCRONIZANDO CON BASE DE DATOS... ---")
            with yt_dlp.YoutubeDL(ydl_opts_list) as ydl:
                info = ydl.extract_info(url, download=False)
                
                pl_title = info.get('title', 'Lista Sin Titulo')
                # Registrar Playlist en DB
                playlist_id = self.db.get_or_create_playlist(url, pl_title)
                
                entries = []
                if 'entries' in info:
                    entries = list(info['entries'])
                    self.log(f"Playlist encontrada: {len(entries)} elementos.")
                else:
                    entries = [info]
                
                # Guardar videos en DB (solo los nuevos)
                added = self.db.add_videos_to_playlist(playlist_id, entries)
                self.log(f"Nuevos videos agregados a la cola: {added}")

        except Exception as e:
            self.log(f"Error al analizar URL: {e}")
            return

        # 2. Bucle de Descarga basado en DB
        # Obtenemos solo los pendientes
        pending_videos = self.db.get_pending_videos(playlist_id)
        total_pending = len(pending_videos)
        
        if total_pending == 0:
            self.log("¡Todos los videos de esta lista ya están descargados!")
            return

        self.log(f"--- INICIANDO DESCARGA DE {total_pending} VIDEOS PENDIENTES ---")

        for i, (db_id, title, video_url) in enumerate(pending_videos):
            if self.stop_flag:
                self.log("⛔ PROCESO DETENIDO POR EL USUARIO.")
                break

            # --- Lógica Anti-Bloqueo (Rate Limit) ---
            # Si estamos en 'modo pausa' por rate limit, el bucle debe gestionar la espera
            while self.is_paused_by_limit:
                if self.stop_flag: break
                self.log("⏳ Esperando liberación de IP (Rate Limit)...")
                # Esperamos bloques de 1 minuto para no congelar la UI si el usuario cancela
                for _ in range(60): 
                    if self.stop_flag: break
                    time.sleep(1)
                
                # Intentamos reanudar tras la espera
                self.is_paused_by_limit = False 

            self.log(f"\n[{i+1}/{total_pending}] Procesando: {title}")

            # Configuración yt-dlp
            ydl_opts_down = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(path, f'{name_template}.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio', 
                    'preferredcodec': config.get('format'), 
                    'preferredquality': config.get('bitrate')
                }, {'key': 'FFmpegMetadata', 'add_metadata': True}],
                'quiet': True, 'no_warnings': True,
                'logger': ConsoleLogger(self.log),
            }
            if cookie: ydl_opts_down['cookiefile'] = cookie

            # --- INICIO LÓGICA DE REINTENTOS ---
            max_retries = 3
            attempt = 0
            success = False

            while attempt < max_retries:
                if self.stop_flag: break
                attempt += 1
                
                # Intentar descarga
                status, err_msg = self._download_safe(ydl_opts_down, video_url)
                
                if status == "OK":
                    self.db.update_video_status(db_id, "COMPLETED", filepath="Ok")
                    success = True
                    break # Salir del bucle de reintentos
                
                elif status == "RATE_LIMIT":
                    self.log("⚠️ DETECTADO BLOQUEO DE YOUTUBE (429).")
                    self.log("💤 El sistema entrará en pausa automática por 5 minutos.")
                    self.is_paused_by_limit = True
                    self._wait_cooldown(minutes=5)
                    # Si hay rate limit, rompemos el bucle de reintentos de este video
                    # para que el bucle principal maneje la pausa al inicio del siguiente ciclo
                    # (o reintente este mismo si la lógica lo permitiera, pero aquí pasamos al siguiente).
                    break 

                else:
                    # Caso ERROR (Ej: Video Unavailable)
                    if attempt < max_retries:
                        self.log(f"⚠️ Error en intento {attempt}/{max_retries}: {err_msg}")
                        self.log("🔄 Reintentando en 5 segundos...")
                        time.sleep(5)
                    else:
                        # Si llegamos aquí, se agotaron los intentos
                        self.log(f"❌ Falló tras {max_retries} intentos. Saltando video.")
                        self.db.update_video_status(db_id, "ERROR", error_msg=err_msg)
            
            # --- FIN LÓGICA DE REINTENTOS ---
            
            # Pausa humana normal entre videos exitosos (o saltados)
            time.sleep(random.uniform(2, 5))

        self.log("\n--- TAREA FINALIZADA O PAUSADA ---")

    def _download_safe(self, opts, url):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
                return "OK", ""
        except DownloadError as e:
            msg = str(e)
            # Detección de palabras clave de bloqueo
            if "HTTP Error 429" in msg or "rate-limited" in msg or "Try again later" in msg:
                return "RATE_LIMIT", msg
            return "ERROR", msg
        except Exception as e:
            return "CRITICAL", str(e)

    def _wait_cooldown(self, minutes):
        """Espera activa que permite cancelar desde la UI"""
        seconds = minutes * 60
        for s in range(seconds):
            if self.stop_flag: return
            if s % 60 == 0:
                remaining = minutes - (s // 60)
                self.log(f"⏳ Enfriando motor... {remaining} minutos restantes.")
            time.sleep(1)