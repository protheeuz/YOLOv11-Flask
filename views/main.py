import os
import cv2
from flask import Blueprint, Response, flash, render_template, redirect, url_for, request, jsonify, current_app
from flask_login import login_required, current_user, login_user
from database import get_db
from models import User
from detection import detect_and_label, generate_frames, process_video
from werkzeug.utils import secure_filename

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    user_id = current_user.id

    # Query statistik deteksi dari database
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS daily 
        FROM detections 
        WHERE user_id = %s AND DATE(time) = CURDATE()
    """, (user_id,))
    daily_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) AS weekly 
        FROM detections 
        WHERE user_id = %s AND YEARWEEK(time) = YEARWEEK(NOW())
    """, (user_id,))
    weekly_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) AS monthly 
        FROM detections 
        WHERE user_id = %s AND MONTH(time) = MONTH(NOW()) AND YEAR(time) = YEAR(NOW())
    """, (user_id,))
    monthly_count = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'home/index.html',
        daily_count=daily_count,
        weekly_count=weekly_count,
        monthly_count=monthly_count
    )

@main_bp.route('/profile')
@login_required
def profile():
    return render_template('home/profile.html')

@main_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    name = request.form['name']
    address = request.form['address']
    about = request.form['about']
    phone = request.form.get('phone')

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET name = %s, address = %s, about = %s, phone = %s
        WHERE id = %s
    """, (name, address, about, phone, current_user.id))

    connection.commit()
    cursor.close()

    user = User.get(current_user.id)
    login_user(user)

    flash('Profil berhasil diperbarui.', 'success')
    return redirect(url_for('main.profile'))

@main_bp.route('/update_profile_image', methods=['POST'])
@login_required
def update_profile_image():
    profile_image = request.files.get('profile_image')
    if profile_image:
        profile_image_filename = save_profile_image(profile_image)

        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE users
            SET profile_image = %s
            WHERE id = %s
        """, (profile_image_filename, current_user.id))

        connection.commit()
        cursor.close()

        user = User.get(current_user.id)
        login_user(user)

        flash('Foto profil berhasil diperbarui.', 'success')
    return redirect(url_for('main.profile'))

def save_profile_image(image_file):
    filename = secure_filename(image_file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    image_file.save(filepath)
    return 'uploads/' + filename

@main_bp.route('/riwayat')
@login_required
def riwayat():
    user_id = current_user.id

    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT time, confidence, label, image_path
        FROM detections
        WHERE user_id = %s
        ORDER BY time DESC
    """, (user_id,))
    
    # Mengubah hasil query menjadi list of dictionaries
    detection_history = [
        {
            'time': row[0],
            'confidence': row[1],
            'label': row[2],
            'image_path': row[3]
        }
        for row in cursor.fetchall()
    ]
    cursor.close()

    return render_template('home/riwayat.html', detection_history=detection_history)

@main_bp.route('/list-detections')
@login_required
def list_detections():
    user_id = current_user.id

    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT confidence, time, image_path
        FROM detections
        WHERE user_id = %s AND label = 'fall'
        ORDER BY time DESC
    """, (user_id,))
    
    detections = [
        {
            'confidence': row[0],
            'time': row[1],
            'image_path': row[2]
        }
        for row in cursor.fetchall()
    ]
    cursor.close()

    return render_template('home/list_detections.html', detections=detections)

@main_bp.route('/stream/<path:video_source>')
@login_required
def stream(video_source):
    """
    Streaming video dengan deteksi bounding box.
    """
    def generate():
        cap = cv2.VideoCapture(video_source)
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame = detect_and_label(frame, current_user.id)

            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        cap.release()

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@main_bp.route('/detect/upload', methods=['GET', 'POST'])
@login_required
def detect_upload():
    """
    Proses video yang diunggah.
    """
    if request.method == 'POST':
        video_file = request.files.get('video')
        if not video_file:
            flash('Harap unggah file video.', 'danger')
            return redirect(url_for('main.detect_upload'))

        filename = secure_filename(video_file.filename)
        input_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        video_file.save(input_path)

        output_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"output_{filename}")
        process_video(input_path, output_path, current_user.id)

        flash('Video berhasil diproses. Silakan unduh hasilnya.', 'success')
        return render_template('home/detect_upload.html', output_path=f"uploads/output_{filename}")
    return render_template('home/detect_upload.html')

@main_bp.route('/detect/realtime_rtsp', methods=['POST'])
@login_required
def detect_realtime_rtsp():
    """
    Proses deteksi real-time dengan RTSP.
    """
    rtsp_url = request.form.get('rtsp_url')
    if not rtsp_url:
        flash("URL RTSP diperlukan untuk memulai deteksi real-time.", "danger")
        return redirect(url_for('main.detect_upload'))

    return render_template(
        'home/detect_upload.html',
        rtsp_url=rtsp_url
    )