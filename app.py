import os
import warnings
from dotenv import load_dotenv

# Menonaktifkan operasi khusus oneDNN untuk TensorFlow
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Mengurangi log peringatan TensorFlow

# Mengabaikan peringatan DeprecationWarning
warnings.filterwarnings("ignore", category=DeprecationWarning)

import tensorflow as tf
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user, login_required
from config import Config
from database import close_db
from views.auth import auth_bp
from views.main import main_bp
from models import User

# Load variabel lingkungan dari file .env
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'  # Tentukan endpoint login

# Tambahkan konfigurasi 'UPLOAD_FOLDER'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

# Daftarkan blueprint untuk autentikasi dan rute utama
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(main_bp)

@app.teardown_appcontext
def teardown_db(exception):
    # Tutup koneksi database saat aplikasi selesai
    close_db()

@app.route('/')
@login_required
def index():
    return render_template('home/index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)