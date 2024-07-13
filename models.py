from flask_login import UserMixin
from database import get_db

class User(UserMixin):
    def __init__(self, id, nik, name, email, password):
        self.id = id
        self.nik = nik
        self.name = name
        self.email = email
        self.password = password

    @staticmethod
    def get(user_id):
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("SELECT id, nik, name, email, password FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        if not user:
            return None
        return User(id=user[0], nik=user[1], name=user[2], email=user[3], password=user[4])