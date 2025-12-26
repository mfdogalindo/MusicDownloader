import sqlite3
import datetime

class DatabaseManager:
    def __init__(self, db_name="downloads.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        
        # 1. Tabla de Configuración (NUEVA)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, 
                value TEXT
            )
        ''')

        # Tabla de Playlists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                created_at TIMESTAMP,
                last_updated TIMESTAMP
            )
        ''')
        
        # Tabla de Videos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER,
                video_id TEXT,
                title TEXT,
                url TEXT,
                status TEXT DEFAULT 'PENDING', 
                error_msg TEXT,
                filepath TEXT,
                FOREIGN KEY(playlist_id) REFERENCES playlists(id),
                UNIQUE(playlist_id, video_id)
            )
        ''')
        self.conn.commit()

    # --- MÉTODOS DE CONFIGURACIÓN (NUEVOS) ---
    def save_setting(self, key, value):
        """Guarda o actualiza una configuración individual."""
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (str(key), str(value)))
        self.conn.commit()

    def load_settings(self):
        """Devuelve un diccionario con toda la configuración guardada."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        return {row[0]: row[1] for row in cursor.fetchall()}

    # --- MÉTODOS DE PLAYLIST Y VIDEO ---
    def get_or_create_playlist(self, url, title="Unknown"):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM playlists WHERE url = ?", (url,))
        row = cursor.fetchone()
        if row:
            return row[0]
        else:
            now = datetime.datetime.now()
            cursor.execute("INSERT INTO playlists (url, title, created_at, last_updated) VALUES (?, ?, ?, ?)",
                           (url, title, now, now))
            self.conn.commit()
            return cursor.lastrowid

    def add_videos_to_playlist(self, playlist_id, entries):
        cursor = self.conn.cursor()
        count = 0
        for entry in entries:
            if not entry: continue
            vid_id = entry.get('id')
            title = entry.get('title', 'Unknown')
            web_url = entry.get('url') or entry.get('webpage_url')
            if not web_url and vid_id:
                web_url = f"https://www.youtube.com/watch?v={vid_id}"

            # Intentamos insertar. Si ya existe (por UNIQUE constraint), lo ignoramos.
            try:
                cursor.execute('''
                    INSERT INTO videos (playlist_id, video_id, title, url, status) 
                    VALUES (?, ?, ?, ?, 'PENDING')
                ''', (playlist_id, vid_id, title, web_url))
                count += 1
            except sqlite3.IntegrityError:
                pass
        self.conn.commit()
        return count

    def get_pending_videos(self, playlist_id):
        cursor = self.conn.cursor()
        # Solo trae videos que no estén completados
        cursor.execute("SELECT id, title, url, video_id, filepath FROM videos WHERE playlist_id = ? AND status != 'COMPLETED'", (playlist_id,))
        return cursor.fetchall()
    
    def get_completed_videos(self, playlist_id):
        """Para verificar si existen físicamente."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, filepath FROM videos WHERE playlist_id = ? AND status = 'COMPLETED'", (playlist_id,))
        return cursor.fetchall()

    def update_video_status(self, db_id, status, error_msg="", filepath=""):
        cursor = self.conn.cursor()
        # Actualizamos también el filepath real
        cursor.execute('''
            UPDATE videos SET status = ?, error_msg = ?, filepath = ? WHERE id = ?
        ''', (status, error_msg, filepath, db_id))
        self.conn.commit()