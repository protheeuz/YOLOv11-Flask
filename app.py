import cv2
import numpy as np
import mysql.connector
import face_recognition
import qrcode
from flask import Flask, request, jsonify, send_file, redirect, url_for
import io
from datetime import datetime
from dotenv import load_dotenv
import os

# Ambil variabel lingkungan dari file .env
load_dotenv()

app = Flask(__name__)

# Koneksi ke database MySQL
def connect_db():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

@app.route('/register', methods=['POST'])
def register():
    nik = request.form['nik']
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO users (nik, name, email, password) VALUES (%s, %s, %s, %s)", (nik, name, email, password))
    connection.commit()
    user_id = cursor.lastrowid
    cursor.close()
    
    # Ambil gambar dari webcam
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    
    # Deteksi wajah dan encoding wajah
    face_locations = face_recognition.face_locations(frame)
    face_encodings = face_recognition.face_encodings(frame, face_locations)
    
    if face_encodings:
        face_encoding = face_encodings[0]
        cursor = connection.cursor()
        cursor.execute("INSERT INTO faces (user_id, encoding) VALUES (%s, %s)", (user_id, face_encoding.tobytes()))
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({"status": "sukses", "user_id": user_id})
    else:
        connection.close()
        return jsonify({"status": "gagal", "pesan": "Wajah tidak ditemukan"}), 400

@app.route('/login', methods=['POST'])
def login():
    nik = request.form['nik']
    password = request.form['password']
    
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM users WHERE nik=%s AND password=%s", (nik, password))
    user = cursor.fetchone()
    if user:
        cursor.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user[0],))
        connection.commit()
        
        # Cek apakah sudah melakukan pengecekan kesehatan hari ini
        check_date = datetime.now().date()
        cursor.execute("SELECT completed FROM health_checks WHERE user_id=%s AND check_date=%s", (user[0], check_date))
        health_check = cursor.fetchone()
        
        if health_check and health_check[0]:
            cursor.close()
            connection.close()
            return redirect(url_for('dashboard', user_id=user[0]))
        else:
            if not health_check:
                cursor.execute("INSERT INTO health_checks (user_id, check_date) VALUES (%s, %s)", (user[0], check_date))
                connection.commit()
            
            cursor.close()
            connection.close()
            return redirect(url_for('health_check', user_id=user[0]))
    else:
        cursor.close()
        connection.close()
        return jsonify({"status": "gagal", "pesan": "NIK atau password salah"}), 401

@app.route('/login_face', methods=['POST'])
def login_face():
    # Ambil gambar dari webcam untuk deteksi wajah
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()

    # Deteksi wajah dan encoding wajah
    face_locations = face_recognition.face_locations(frame)
    face_encodings = face_recognition.face_encodings(frame, face_locations)
    
    if face_encodings:
        face_encoding = face_encodings[0]
        user_id = recognize_face(face_encoding)
        
        if user_id:
            connection = connect_db()
            cursor = connection.cursor()
            cursor.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user_id,))
            connection.commit()
            
            # Cek apakah sudah melakukan pengecekan kesehatan hari ini
            check_date = datetime.now().date()
            cursor.execute("SELECT completed FROM health_checks WHERE user_id=%s AND check_date=%s", (user_id, check_date))
            health_check = cursor.fetchone()
            
            if health_check and health_check[0]:
                cursor.close()
                connection.close()
                return redirect(url_for('dashboard', user_id=user_id))
            else:
                if not health_check:
                    cursor.execute("INSERT INTO health_checks (user_id, check_date) VALUES (%s, %s)", (user_id, check_date))
                    connection.commit()
                
                cursor.close()
                connection.close()
                return redirect(url_for('health_check', user_id=user_id))
        else:
            return jsonify({"status": "gagal", "pesan": "Wajah tidak dikenali"}), 401
    else:
        return jsonify({"status": "gagal", "pesan": "Tidak ada wajah yang ditemukan"}), 400

@app.route('/generate_qr', methods=['GET'])
def generate_qr():
    nik = request.args.get('nik')
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM users WHERE nik=%s", (nik,))
    user = cursor.fetchone()
    cursor.close()
    connection.close()

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

@app.route('/login_qr', methods=['POST'])
def login_qr():
    qr_code = request.form['qr_code']
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM users WHERE nik=%s", (qr_code,))
    user = cursor.fetchone()
    if user:
        cursor.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user[0],))
        connection.commit()
        
        # Cek apakah sudah melakukan pengecekan kesehatan hari ini
        check_date = datetime.now().date()
        cursor.execute("SELECT completed FROM health_checks WHERE user_id=%s AND check_date=%s", (user[0], check_date))
        health_check = cursor.fetchone()
        
        if health_check and health_check[0]:
            cursor.close()
            connection.close()
            return redirect(url_for('dashboard', user_id=user[0]))
        else:
            if not health_check:
                cursor.execute("INSERT INTO health_checks (user_id, check_date) VALUES (%s, %s)", (user[0], check_date))
                connection.commit()
            
            cursor.close()
            connection.close()
            return redirect(url_for('health_check', user_id=user[0]))
    else:
        cursor.close()
        connection.close()
        return jsonify({"status": "gagal", "pesan": "QR Code tidak valid"}), 401

@app.route('/sensor_data', methods=['POST'])
def sensor_data():
    user_id = request.form['user_id']
    heart_rate = request.form['heart_rate']
    oxygen_level = request.form['oxygen_level']
    temperature = request.form['temperature']
    activity_level = request.form['activity_level']
    
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("""
        INSERT INTO sensor_data (user_id, heart_rate, oxygen_level, temperature, activity_level)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, heart_rate, oxygen_level, temperature, activity_level))
    
    # Tandai pengecekan kesehatan sudah selesai untuk hari ini
    check_date = datetime.now().date()
    cursor.execute("UPDATE health_checks SET completed = TRUE WHERE user_id = %s AND check_date = %s", (user_id, check_date))
    
    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({"status": "sukses"})

@app.route('/dashboard/<int:user_id>')
def dashboard(user_id):
    # Tampilkan halaman dashboard
    return f"Selamat datang di dashboard, user {user_id}!"

@app.route('/health_check/<int:user_id>')
def health_check(user_id):
    # Tampilkan halaman pengecekan kesehatan
    return f"Silakan selesaikan pengecekan kesehatan Anda, user {user_id}!"

def recognize_face(face_encoding):
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT user_id, encoding FROM faces")
    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    for row in rows:
        user_id, stored_encoding = row
        stored_encoding = np.frombuffer(stored_encoding, dtype=np.float64)
        matches = face_recognition.compare_faces([stored_encoding], face_encoding)
        if matches[0]:
            return user_id
    return None

if __name__ == '__main__':
    app.run(debug=True)