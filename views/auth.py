import cv2
import numpy as np
from flask import Blueprint, request, jsonify, redirect, url_for, render_template, send_file
from flask_login import login_user, logout_user, login_required
from database import get_db
from deepface import DeepFace
from datetime import datetime
import qrcode
import io
from models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nik = request.form['nik']
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("INSERT INTO users (nik, name, email, password) VALUES (%s, %s, %s, %s)", (nik, name, email, password))
        connection.commit()
        user_id = cursor.lastrowid
        cursor.close()

        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()

        try:
            result = DeepFace.represent(frame, model_name='Facenet')
            face_encoding = result[0]["embedding"]
            cursor = connection.cursor()
            cursor.execute("INSERT INTO faces (user_id, encoding) VALUES (%s, %s)", (user_id, str(face_encoding)))
            connection.commit()
            cursor.close()
            return jsonify({"status": "sukses", "user_id": user_id})
        except Exception as e:
            return jsonify({"status": "gagal", "pesan": "Wajah tidak ditemukan"}), 400
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nik = request.form['nik']
        password = request.form['password']
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("SELECT id, password FROM users WHERE nik=%s", (nik,))
        user_data = cursor.fetchone()

        if user_data and user_data[1] == password:
            user = User.get(user_data[0])
            login_user(user)
            return redirect(url_for('main.dashboard', user_id=user_data[0]))

        return render_template('login.html', msg='NIK atau password salah')

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/login_face', methods=['POST'])
def login_face():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()

    try:
        result = DeepFace.represent(frame, model_name='Facenet')
        face_encoding = result[0]["embedding"]
        user_id = recognize_face(face_encoding)

        if user_id:
            connection = get_db()
            cursor = connection.cursor()
            cursor.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user_id,))
            connection.commit()

            check_date = datetime.now().date()
            cursor.execute("SELECT completed FROM health_checks WHERE user_id=%s AND check_date=%s", (user_id, check_date))
            health_check = cursor.fetchone()

            cursor.close()
            return jsonify({"status": "sukses", "user_id": user_id})
        else:
            return jsonify({"status": "gagal", "pesan": "Wajah tidak dikenali"}), 401
    except Exception as e:
        return jsonify({"status": "gagal", "pesan": "Tidak ada wajah yang ditemukan"}), 400

@auth_bp.route('/generate_qr', methods=['GET'])
def generate_qr():
    nik = request.args.get('nik')
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM users WHERE nik=%s", (nik,))
    user = cursor.fetchone()
    cursor.close()

    if user:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(nik)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf)
        buf.seek(0)

        return send_file(buf, mimetype='image/png')
    else:
        return jsonify({"status": "gagal", "pesan": "NIK tidak ditemukan"}), 404

@auth_bp.route('/login_qr', methods=['POST'])
def login_qr():
    qr_code = request.form['qr_code']
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM users WHERE nik=%s", (qr_code,))
    user = cursor.fetchone()
    if user:
        user_id = user[0]
        cursor.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user_id,))
        connection.commit()

        check_date = datetime.now().date()
        cursor.execute("SELECT completed FROM health_checks WHERE user_id=%s AND check_date=%s", (user_id, check_date))
        health_check = cursor.fetchone()

        cursor.close()
        return jsonify({"status": "sukses", "user_id": user_id})
    else:
        cursor.close()
        return jsonify({"status": "gagal", "pesan": "QR Code tidak valid"}), 401

def recognize_face(face_encoding):
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("SELECT user_id, encoding FROM faces")
    rows = cursor.fetchall()
    cursor.close()

    for row in rows:
        user_id, stored_encoding = row
        stored_encoding = np.frombuffer(eval(stored_encoding), dtype=np.float64)
        if DeepFace.verify(face_encoding, stored_encoding, model_name='Facenet'):
            return user_id
    return None