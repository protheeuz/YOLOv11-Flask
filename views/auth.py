import cv2
import numpy as np
from flask import Blueprint, request, jsonify, redirect, session, url_for, render_template, send_file, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
import requests
from sklearn.metrics.pairwise import cosine_similarity
from database import get_db
from deepface import DeepFace
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
import json
import bcrypt
import qrcode
import io
from models import User
import random
import string
import logging

auth_bp = Blueprint('auth', __name__)

def generate_unique_code():
    return ''.join(random.choices(string.digits, k=4))

def generate_session_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

logging.basicConfig(level=logging.DEBUG)

def encode_face(face_encoding):
    return json.dumps(face_encoding)

def decode_face(stored_encoding):
    return np.array(json.loads(stored_encoding))

def calculate_cosine_similarity(embedding1, embedding2):
    embedding1 = np.array(embedding1).reshape(1, -1)
    embedding2 = np.array(embedding2).reshape(1, -1)
    return cosine_similarity(embedding1, embedding2)[0][0]

def generate_reset_token(user_id):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(user_id, salt='password-reset-salt')

def verify_reset_token(token, expiration=3600):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        user_id = s.loads(token, salt='password-reset-salt', max_age=expiration)
    except (SignatureExpired, BadSignature):
        return None
    return user_id

def send_reset_password_email(email, reset_link, name):
    html_content = render_template('email_templates/reset_password_email.html', reset_link=reset_link, name=name)
    message = Mail(
        from_email=current_app.config['SENDGRID_DEFAULT_FROM'],
        to_emails=email,
        subject='Reset Password Kamu',
        html_content=html_content
    )
    try:
        sg = SendGridAPIClient(current_app.config['SENDGRID_API_KEY'])
        response = sg.send(message)
        logging.info(f"Email sent to {email} with status code {response.status_code}")
    except Exception as e:
        logging.error(f"Error sending email: {e}")

############################################################
############### BATAS ROUTES AUTHENTICATION ################
############################################################

@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        
        connection = get_db()
        cursor = connection.cursor()
        
        cursor.execute("SELECT id, email, name FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        
        if user:
            user_id, email, name = user
            reset_token = generate_reset_token(user_id)
            reset_link = url_for('auth.reset_password', token=reset_token, _external=True)
            send_reset_password_email(email, reset_link, name)
            return render_template('auth/forgot_password.html', success='Link reset password telah dikirim ke email Anda.')
        else:
            return render_template('auth/forgot_password.html', error='Email yang dimasukkan tidak terdaftar.')
    
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user_id = verify_reset_token(token)
    if not user_id:
        return render_template('auth/reset_password.html', error='Token reset password tidak valid atau telah kadaluarsa.')

    if request.method == 'POST':
        password = request.form['password']
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_password, user_id))
        connection.commit()
        cursor.close()

        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', token=token)

@auth_bp.route('/check_existing_user', methods=['POST'])
def check_existing_user():
    email = request.form['email']
    
    connection = get_db()
    cursor = connection.cursor()
    
    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    existing_user = cursor.fetchone()
    cursor.close()

    if existing_user:
        return jsonify({"status": "gagal", "pesan": "Email sudah terdaftar"}), 400
    
    return jsonify({"status": "sukses"})


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        registration_date = datetime.now()
        unique_code = generate_unique_code()

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        connection = get_db()
        cursor = connection.cursor()
        
        try:
            # Cek apakah email sudah terdaftar
            cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            existing_user = cursor.fetchone()
            if existing_user:
                cursor.close()
                return jsonify({"status": "gagal", "pesan": "Email sudah terdaftar"}), 400

            # Simpan data pengguna baru ke tabel users tanpa face registration
            cursor.execute("INSERT INTO users (name, email, password, registration_date, unique_code, face_registered) VALUES (%s, %s, %s, %s, %s, %s)",
                           (name, email, hashed_password, registration_date, unique_code, False))
            connection.commit()
            user_id = cursor.lastrowid

            cursor.close()

            # Kirimkan user_id kembali ke klien untuk digunakan saat mendaftarkan wajah
            return jsonify({"status": "sukses", "user_id": user_id})

        except Exception as e:
            # Menangkap error jika terjadi masalah dengan database
            logging.error(f"Error during registration: {str(e)}")
            cursor.close()
            return jsonify({"status": "gagal", "pesan": "Terjadi kesalahan saat mendaftar, coba lagi nanti."}), 500
    else:
        return render_template('auth/register.html') 

@auth_bp.route('/register_face', methods=['POST'])
def register_face():
    face_image = request.files['face_image']
    user_id = request.form['user_id']
    if not user_id:
        logging.error("User ID is missing in register_face.")
        return jsonify({"status": "gagal", "pesan": "User ID tidak ditemukan"}), 400

    npimg = np.frombuffer(face_image.read(), np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    try:
        result = DeepFace.represent(img, model_name='Facenet', enforce_detection=False)
        face_encoding = result[0]["embedding"]

        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("INSERT INTO faces (user_id, encoding) VALUES (%s, %s)", (user_id, encode_face(face_encoding)))
        connection.commit()

        cursor.execute("UPDATE users SET face_registered=%s WHERE id=%s", (True, user_id))
        connection.commit()
        cursor.close()

        return jsonify({"status": "sukses"})
    except Exception as e:
        logging.exception("Terjadi kesalahan saat memproses wajah")
        return jsonify({"status": "gagal", "pesan": "Wajah tidak ditemukan"}), 400

@auth_bp.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        logging.debug(f"Email yang dimasukkan: {email}")
        logging.debug(f"Password yang dimasukkan: {password}")

        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("SELECT id, password FROM users WHERE email=%s", (email,))
        user_data = cursor.fetchone()

        logging.debug(f"Mencari user dengan email: {email}")

        if user_data:
            stored_password = user_data[1]
            logging.debug(f"Password yang disimpan: {stored_password}")
            password_correct = bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8'))

            if password_correct:
                user = User.get(user_data[0])
                if not user:
                    logging.error(f"User dengan ID {user_data[0]} tidak ditemukan setelah login.")
                    return jsonify({"status": "gagal", "message": "User tidak ditemukan"}), 404

                # Proses login berhasil
                login_user(user)
                session['user_id'] = user_data[0]
                session['session_token'] = generate_session_token()

                cursor.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user_data[0],))
                connection.commit()

                logging.debug(f"User data ditemukan: {user_data}")
                logging.debug(f"Password yang dimasukkan: {password}")
                logging.debug(f"Password yang disimpan: {stored_password}")

                # Mengirimkan respons sukses yang lengkap
                return jsonify({
                    "status": "sukses",
                    "user_id": user_data[0],
                    "redirect": url_for('main.index')
                })

            else:
                logging.error("Password yang dimasukkan salah.")
                return jsonify({"status": "gagal", "message": "Email atau password salah"}), 401

        else:
            logging.error(f"User dengan email {email} tidak ditemukan.")
            return jsonify({"status": "gagal", "message": "Email atau password salah"}), 401

        cursor.close()

    return render_template('auth/login.html')

@auth_bp.route('/login_face', methods=['POST'])
def login_face():
    logging.debug("Memulai proses login wajah")
    
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        logging.error("Tidak dapat mengakses kamera")
        return jsonify({"status": "gagal", "pesan": "Tidak dapat mengakses kamera"}), 400

    ret, frame = cap.read()
    cap.release()

    if not ret:
        logging.error("Tidak dapat mengambil frame dari kamera")
        return jsonify({"status": "gagal", "pesan": "Tidak dapat mengambil frame dari kamera"}), 400

    try:
        result = DeepFace.represent(frame, model_name='Facenet', enforce_detection=False)
        if not result or "embedding" not in result[0]:
            logging.error("DeepFace gagal mendeteksi wajah atau menghasilkan representasi wajah.")
            return jsonify({"status": "gagal", "pesan": "Tidak ada wajah yang terdeteksi atau wajah tidak dikenali"}), 400
        face_encoding = result[0]["embedding"]
        logging.debug(f"Representasi wajah berhasil diambil: {face_encoding}")

        user_id = recognize_face(face_encoding)
        if user_id:
            logging.debug(f"Wajah dikenali, user_id: {user_id}")
            connection = get_db()
            cursor = connection.cursor()
            cursor.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user_id,))
            connection.commit()

            user = User.get(user_id)
            login_user(user)
            
            session['user_id'] = user_id
            session['session_token'] = generate_session_token()
            cursor.close()

            return jsonify({
                "status": "sukses",
                "user_id": user_id,
                "redirect": url_for('main.index') 
            })

        else:
            logging.error("Wajah tidak dikenali")
            return jsonify({"status": "gagal", "pesan": "Wajah tidak dikenali"}), 401
    except Exception as e:
        logging.exception("Terjadi kesalahan saat memproses wajah")
        return jsonify({"status": "gagal", "pesan": "Terjadi kesalahan saat memproses wajah"}), 400

@auth_bp.route('/login_qr', methods=['POST'])
def login_qr():
    data = request.get_json()
    qr_code = data.get('qr_code')  
    user_code = data.get('user_code') 
    
    if not qr_code or not user_code:
        return jsonify({"status": "gagal", "pesan": "QR Code atau Kode Unik tidak ditemukan"}), 400

    connection = get_db()
    cursor = connection.cursor()
    
    cursor.execute("SELECT id, unique_code FROM users WHERE email=%s", (qr_code,))
    user = cursor.fetchone()
    
    if user:
        if user_code == user[1]:  # Memeriksa apakah kode unik cocok dengan yang ada di database
            user_id = user[0]
            cursor.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user_id,))
            connection.commit()

            user = User.get(user_id)
            login_user(user)
            
            session['user_id'] = user_id
            session['session_token'] = generate_session_token()

            cursor.close()
            return jsonify({
                "status": "sukses",
                "user_id": user_id,
                "redirect": url_for('main.index') 
            })

        else:
            cursor.close()
            return jsonify({"status": "gagal", "pesan": "Kode unik tidak valid"}), 401
    else:
        cursor.close()
        return jsonify({"status": "gagal", "pesan": "QR Code tidak valid"}), 401

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/generate_qr', methods=['GET'])
def generate_qr():
    email = request.args.get('email')
    if not email:
        return jsonify({"status": "gagal", "pesan": "Email tidak ditemukan"}), 404

    connection = get_db()
    cursor = connection.cursor()
    
    cursor.execute("SELECT unique_code FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()
    cursor.close()

    if user:
        unique_code = user[0]
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(unique_code)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf)
        buf.seek(0)

        return send_file(buf, mimetype='image/png')
    else:
        return jsonify({"status": "gagal", "pesan": "Email tidak ditemukan"}), 404


def recognize_face(face_encoding):
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("SELECT user_id, encoding FROM faces")
    rows = cursor.fetchall()
    cursor.close()

    for row in rows:
        user_id, stored_encoding = row
        stored_encoding = decode_face(stored_encoding)
        similarity = calculate_cosine_similarity(face_encoding, stored_encoding)
        if similarity > 0.9:  
            return user_id
    return None
    
# @auth_bp.route('/send_session_token', methods=['POST'])
# @login_required
# def send_session_token():
#     data = request.get_json()
#     esp32_ip = data.get('esp32_ip')
#     session_token = session.get('session_token')

#     response = requests.post(f'http://{esp32_ip}/set_session_token', json={'session_token': session_token})

#     if response.status_code == 200:
#         return jsonify({"status": "sukses"})
#     else:
#         return jsonify({"status": "gagal"}), 500