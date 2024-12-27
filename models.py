from flask_login import UserMixin
from database import get_db
from datetime import datetime

class User(UserMixin):
    def __init__(self, id, name, email, address=None, about=None, profile_image=None):
        self.id = id
        self.name = name
        self.email = email
        self.address = address
        self.about = about
        self.profile_image = profile_image

    @staticmethod
    def get(user_id):
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, name, email, address, about, profile_image
            FROM users 
            WHERE id=%s
        """, (user_id,))
        user = cursor.fetchone()
        cursor.close()
        if not user:
            return None
        return User(user[0], user[1], user[2], user[3], user[4], user[5])

class Notification:
    def __init__(self, user_id, message, created_at, read=False):
        self.user_id = user_id
        self.message = message
        self.created_at = created_at
        self.read = read

    @staticmethod
    def get_new_notifications():
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT u.name, n.message, TIMESTAMPDIFF(MINUTE, n.created_at, NOW()) as time_ago
            FROM notifications n
            JOIN users u ON n.user_id = u.id
            WHERE n.read = FALSE
            ORDER BY n.created_at DESC
        """)
        notifications = cursor.fetchall()
        cursor.close()
        return [{'user_name': notif[0], 'message': notif[1], 'time_ago': f'{notif[2]} min'} for notif in notifications]

    @staticmethod
    def get_old_notifications():
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT u.name, n.message, TIMESTAMPDIFF(MINUTE, n.created_at, NOW()) as time_ago
            FROM notifications n
            JOIN users u ON n.user_id = u.id
            WHERE n.read = TRUE
            ORDER BY n.created_at DESC
        """)
        notifications = cursor.fetchall()
        cursor.close()
        return [{'user_name': notif[0], 'message': notif[1], 'time_ago': f'{notif[2]} min'} for notif in notifications]