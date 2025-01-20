import os
import threading
from time import sleep
import warnings
from wsgiref import headers
from dotenv import load_dotenv
from flask_cors import CORS

# # Menonaktifkan operasi khusus oneDNN untuk TensorFlow
# os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
# os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Mengurangi log peringatan TensorFlow
# # Mengabaikan peringatan DeprecationWarning
# warnings.filterwarnings("ignore", category=DeprecationWarning)

import requests
from flask import Flask, current_app, render_template, redirect, request, session, url_for
from flask_login import LoginManager, current_user, login_required
from config import Config
from database import close_db, get_db
from detection import cleanup_handlers
from views.auth import auth_bp
from views.main import main_bp
from models import User

# Load variabel lingkungan dari file .env
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = '5f957e6105f189f9974ae631b351b321'
CORS(app, resources={r"/static/uploads/*": {"origins": "*"}})

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login' 

# Tambahkan konfigurasi 'UPLOAD_FOLDER'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['DETECTION_IMAGES_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'detections')
app.config['PUBLIC_URL'] = 'https://hardy-tolerant-kodiak.ngrok-free.app'
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DETECTION_IMAGES_FOLDER'], exist_ok=True)

def setup_cleanup_task(app):
    def cleanup_task():
        with app.app_context():
            while True:
                cleanup_handlers()
                sleep(30) 
                
    cleanup_thread = threading.Thread(target=cleanup_task)
    cleanup_thread.daemon = True
    cleanup_thread.start()

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
    app.run(host='0.0.0.0', port=8080, debug=True)