import logging
import mysql.connector
from flask import g
from config import Config

logging.basicConfig(level=logging.DEBUG)

def connect_db():
    try:
        db_connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        logging.debug("Database connection established.")
        return db_connection
    except mysql.connector.Error as err:
        logging.error(f"Error connecting to the database: {err}")
        raise

def get_db():
    if 'db' not in g:
        g.db = connect_db()
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()