import mysql.connector
from flask import g
from config import Config

def connect_db():
    # Bikin koneksi ke database MySQL
    return mysql.connector.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME
    )

def get_db():
    # Ambil koneksi database, kalau belum ada, bikin baru
    if 'db' not in g:
        g.db = connect_db()
    return g.db

def close_db(e=None):
    # Tutup koneksi database pas request selesai
    db = g.pop('db', None)
    if db is not None:
        db.close()