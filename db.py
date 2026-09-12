import sqlite3
import os
import config

def get_db_path():
    return config.get_config_dir() / "downloads.db"

def init_db():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media_downloads (
            chat_id INTEGER,
            message_id INTEGER,
            status TEXT,
            error_message TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, message_id)
        )
    ''')
    conn.commit()
    conn.close()

def get_status(chat_id: int, message_id: int):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT status FROM media_downloads 
        WHERE chat_id = ? AND message_id = ?
    ''', (chat_id, message_id))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def update_status(chat_id: int, message_id: int, status: str, error_message: str = None):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO media_downloads (chat_id, message_id, status, error_message, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id, message_id) DO UPDATE SET
            status=excluded.status,
            error_message=excluded.error_message,
            updated_at=CURRENT_TIMESTAMP
    ''', (chat_id, message_id, status, error_message))
    conn.commit()
    conn.close()

def get_chat_summary(chat_id: int):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT status, COUNT(*) FROM media_downloads 
        WHERE chat_id = ?
        GROUP BY status
    ''', (chat_id,))
    rows = cursor.fetchall()
    conn.close()
    return dict(rows)
