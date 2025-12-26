import sqlite3
import datetime

class DatabaseManager:
    def __init__(self, db_name="downloads.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # Tabla de Playlists / Sesiones
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
        """Agrega videos a la DB solo si no existen ya para esa playlist."""
        cursor = self.conn.cursor()
        count = 0
        for entry in entries:
            if not entry: continue
            vid_id = entry.get('id')
            title = entry.get('title', 'Unknown')
            # Construir URL
            web_url = entry.get('url') or entry.get('webpage_url')
            if not web_url and vid_id:
                web_url = f"https://www.youtube.com/watch?v={vid_id}"

            try:
                cursor.execute('''
                    INSERT INTO videos (playlist_id, video_id, title, url, status) 
                    VALUES (?, ?, ?, ?, 'PENDING')
                ''', (playlist_id, vid_id, title, web_url))
                count += 1
            except sqlite3.IntegrityError:
                # El video ya existe en esta playlist, lo ignoramos
                pass
        self.conn.commit()
        return count

    def get_pending_videos(self, playlist_id):
        cursor = self.conn.cursor()
        # Retorna videos que están PENDING o que dieron ERROR (para reintentar)
        cursor.execute("SELECT id, title, url FROM videos WHERE playlist_id = ? AND status IN ('PENDING', 'ERROR_DL')", (playlist_id,))
        return cursor.fetchall()

    def update_video_status(self, db_id, status, error_msg="", filepath=""):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE videos SET status = ?, error_msg = ?, filepath = ? WHERE id = ?
        ''', (status, error_msg, filepath, db_id))
        self.conn.commit()