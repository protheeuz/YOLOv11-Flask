from flask_login import UserMixin
from database import get_db

class User(UserMixin):
    def __init__(self, id, nik, name, email, role, address=None, about=None, profile_image=None):
        self.id = id
        self.nik = nik
        self.name = name
        self.email = email
        self.role = role
        self.address = address
        self.about = about
        self.profile_image = profile_image

    @staticmethod
    def get(user_id):
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, nik, name, email, role, address, about, profile_image
            FROM users 
            WHERE id=%s
        """, (user_id,))
        user = cursor.fetchone()
        cursor.close()
        if not user:
            return None
        return User(user[0], user[1], user[2], user[3], user[4], user[5], user[6], user[7])