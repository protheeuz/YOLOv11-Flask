import os
import warnings
from wsgiref import headers
from dotenv import load_dotenv
from flask_cors import CORS

# Menonaktifkan operasi khusus oneDNN untuk TensorFlow
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Mengurangi log peringatan TensorFlow

# Mengabaikan peringatan DeprecationWarning
warnings.filterwarnings("ignore", category=DeprecationWarning)

import requests
import tensorflow as tf
from flask import Flask, current_app, render_template, redirect, request, session, url_for
from flask_login import LoginManager, current_user, login_required
from config import Config
from database import close_db, get_db
from views.auth import auth_bp
from views.main import main_bp
from models import User

# Load variabel lingkungan dari file .env
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = '5f957e6105f189f9974ae631b351b321'
CORS(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login' 

# Tambahkan konfigurasi 'UPLOAD_FOLDER'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
app.config['DETECTION_IMAGES_FOLDER'] = os.path.join(app.root_path, 'static/uploads/detections')


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.context_processor
def inject_user():
    new_logins_count = 0
    if current_user.is_authenticated:
        new_logins_count = get_new_logins_count()
    return dict(current_user=current_user, new_logins_count=new_logins_count)

def get_new_logins_count():
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE last_login >= CURDATE()
    """)
    count = cursor.fetchone()[0]
    cursor.close()
    return count

# Daftarkan blueprint untuk autentikasi dan rute utama
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(main_bp)

@app.teardown_appcontext
def teardown_db(exception):
    close_db()

@app.route('/')
@login_required
def index():
    return render_template('home/index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)