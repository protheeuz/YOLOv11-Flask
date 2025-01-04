import os
import cv2
import logging
import requests
from flask import Blueprint, Response, flash, render_template, redirect, url_for, request, jsonify, current_app
from flask_login import login_required, current_user, login_user
from database import get_db
from models import User
from detection import detect_and_label, generate_frames, process_video
from werkzeug.utils import secure_filename
from datetime import date, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    user_id = current_user.id
    connection = get_db()
    cursor = connection.cursor()

    # Statistik harian, mingguan, bulanan
    cursor.execute("""
        SELECT COUNT(*) AS daily 
        FROM detections 
        WHERE user_id = %s AND DATE(time) = CURDATE()
    """, (user_id,))
    daily_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) AS weekly 
        FROM detections 
        WHERE user_id = %s AND YEARWEEK(time, 1) = YEARWEEK(CURDATE(), 1)
    """, (user_id,))
    weekly_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) AS monthly 
        FROM detections 
        WHERE user_id = %s AND MONTH(time) = MONTH(CURDATE()) AND YEAR(time) = YEAR(CURDATE())
    """, (user_id,))
    monthly_count = cursor.fetchone()[0]

    # Data untuk grafik
    cursor.execute("""
        SELECT DATE(time) AS date, 
               SUM(CASE WHEN DATE(time) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) AS daily, 
               SUM(CASE WHEN YEARWEEK(time, 1) >= YEARWEEK(CURDATE(), 1) - 5 THEN 1 ELSE 0 END) AS weekly, 
               SUM(CASE WHEN DATE_FORMAT(time, '%%Y-%%m') >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 YEAR), '%%Y-%%m') THEN 1 ELSE 0 END) AS monthly 
        FROM detections 
        WHERE user_id = %s 
        GROUP BY DATE(time) 
        ORDER BY date ASC
    """, (user_id,))
    raw_data = {row[0]: {'daily': row[1], 'weekly': row[2], 'monthly': row[3]} for row in cursor.fetchall()}

    # Isi data yang kosong dengan nilai nol
    start_date = min(raw_data.keys(), default=date.today())
    end_date = date.today()
    combined_graph_data = [
        {
            'date': single_date.strftime('%Y-%m-%d'),
            'daily': raw_data.get(single_date, {}).get('daily', 0),
            'weekly': raw_data.get(single_date, {}).get('weekly', 0),
            'monthly': raw_data.get(single_date, {}).get('monthly', 0)
        }
        for single_date in generate_date_range(start_date, end_date)
    ]

    # Parameter paginasi
    limit = 10
    daily_page = int(request.args.get('daily_page', 1))
    weekly_page = int(request.args.get('weekly_page', 1))
    all_page = int(request.args.get('all_page', 1))

    daily_offset = (daily_page - 1) * limit
    weekly_offset = (weekly_page - 1) * limit
    all_offset = (all_page - 1) * limit

    # Log hari ini
    cursor.execute("""
        SELECT time, label AS status 
        FROM detections 
        WHERE user_id = %s AND DATE(time) = CURDATE()
        ORDER BY time DESC
        LIMIT %s OFFSET %s
    """, (user_id, limit, daily_offset))
    daily_logs = [{'time': row[0], 'status': row[1]} for row in cursor.fetchall()]

    # Log minggu ini
    cursor.execute("""
        SELECT time, label AS status 
        FROM detections 
        WHERE user_id = %s AND YEARWEEK(time, 1) = YEARWEEK(CURDATE(), 1)
        ORDER BY time DESC
        LIMIT %s OFFSET %s
    """, (user_id, limit, weekly_offset))
    weekly_logs = [{'time': row[0], 'status': row[1]} for row in cursor.fetchall()]

    # Semua log
    cursor.execute("""
        SELECT time, label AS status 
        FROM detections 
        WHERE user_id = %s
        ORDER BY time DESC
        LIMIT %s OFFSET %s
    """, (user_id, limit, all_offset))
    all_logs = [{'time': row[0], 'status': row[1]} for row in cursor.fetchall()]

    cursor.close()

    # Kalkulasi total halaman
    daily_total_pages = (daily_count // limit) + (1 if daily_count % limit > 0 else 0)
    weekly_total_pages = (weekly_count // limit) + (1 if weekly_count % limit > 0 else 0)
    all_total_pages = (len(all_logs) // limit) + (1 if len(all_logs) % limit > 0 else 0)

    return render_template(
        'home/index.html',
        daily_falls=daily_count,
        weekly_falls=weekly_count,
        monthly_falls=monthly_count,
        daily_logs=daily_logs,
        weekly_logs=weekly_logs,
        all_logs=all_logs,
        daily_page=daily_page,
        weekly_page=weekly_page,
        all_page=all_page,
        daily_total_pages=daily_total_pages,
        weekly_total_pages=weekly_total_pages,
        all_total_pages=all_total_pages,
        daily_falls_percentage=(daily_count / max(weekly_count, 1)) * 100 if weekly_count else 0,
        weekly_falls_percentage=(weekly_count / max(monthly_count, 1)) * 100 if monthly_count else 0,
        monthly_falls_percentage=100,
        combined_graph_data=combined_graph_data 
    )
    
def generate_date_range(start_date, end_date):
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)

    
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
    if request.method == 'POST':
        video_file = request.files.get('video')
        if not video_file:
            flash('Harap unggah file video.', 'danger')
            return redirect(url_for('main.detect_upload'))

        filename = secure_filename(video_file.filename)
        input_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        video_file.save(input_path)

        # Output path relatif terhadap folder static
        output_filename = f"output_{filename}"
        output_path = os.path.join(current_app.config['DETECTION_IMAGES_FOLDER'], output_filename)

        # Proses video
        email_frame_path = process_video(input_path, output_path, current_user.id, save_for_email=True)

        # Ambil deteksi dengan confidence tertinggi dari database
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT time, confidence, image_path
            FROM detections
            WHERE user_id = %s AND label = 'Jatuh'
            ORDER BY confidence DESC
            LIMIT 1
        """, (current_user.id,))
        highest_confidence_fall = cursor.fetchone()
        cursor.close()

        # Kirim laporan jika ada deteksi 'Jatuh'
        if highest_confidence_fall and email_frame_path:
            highest_fall_data = {
                'time': highest_confidence_fall[0],
                'confidence': highest_confidence_fall[1],
                'image_path': email_frame_path
            }
            send_fall_report(
                email=current_user.email,
                phone=current_user.phone, 
                fall_data=highest_fall_data,
                name=current_user.name
            )

        flash('Video berhasil diproses. Silakan unduh hasilnya.', 'success')
        return render_template('home/detect_upload.html', output_path=f'uploads/{output_filename}')
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
    
def send_fall_report(email, phone, fall_data, name):
    """
    Mengirimkan laporan deteksi jatuh melalui email dan WhatsApp (jika nomor telepon tersedia).
    """
    # Kirim laporan melalui email
    html_content = render_template(
        'email_templates/fall_report_email.html',
        name=name,
        time=fall_data['time'],
        confidence=fall_data['confidence'],
        image_url=current_app.config['PUBLIC_URL'] + url_for('static', filename=fall_data['image_path'])
    )
    message = Mail(
        from_email=current_app.config['SENDGRID_DEFAULT_FROM'],
        to_emails=email,
        subject='Laporan Deteksi Jatuh',
        html_content=html_content
    )
    try:
        sg = SendGridAPIClient(current_app.config['SENDGRID_API_KEY'])
        response = sg.send(message)
        logging.info(f"Email sent to {email} with status code {response.status_code}")
    except Exception as e:
        logging.error(f"Error sending email to {email}: {e}")

    # Kirim laporan melalui WhatsApp jika nomor telepon tersedia
    if phone:
        try:
            send_fall_report_whatsapp(phone, fall_data, name)
        except Exception as e:
            logging.error(f"Error sending WhatsApp message to {phone}: {e}")


def send_fall_report_whatsapp(phone, fall_data, name):
    """
    Mengirimkan laporan deteksi jatuh melalui WhatsApp menggunakan WAPISender.
    """
    if not phone:
        logging.info("No phone number provided. Skipping WhatsApp notification.")
        return  # Gak kirim kalau nomor telepon tidak tersedia

    api_url = "https://wapisender.id/api/v5/message/image"
    api_key = current_app.config['WAPISENDER_API_KEY']
    device_key = current_app.config['WAPISENDER_DEVICE_KEY']

    # Validasi file gambar
    image_path = fall_data.get('image_path')
    if not os.path.exists(image_path):
        logging.error(f"File not found: {image_path}")
        return

    # Payload data
    payload = {
        'api_key': api_key,
        'device_key': device_key,
        'destination': phone,
        'caption': (
            f"Halo, {name}!\n\n"
            f"Kami mendeteksi adanya *Jatuh* pada sesi pendeteksian terakhir.\n\n"
            f"Detail deteksi:\n"
            f"- Waktu: {fall_data['time']}\n"
            f"- Confidence: {fall_data['confidence']}%\n\n"
            f"Berikut adalah gambar deteksinya:"
        ),
        'view_once': 'false'
    }

    # Coba kirim gambar
    try:
        with open(image_path, 'rb') as image_file:
            files = {'image': (os.path.basename(image_path), image_file, 'image/jpeg')}
            response = requests.post(api_url, data=payload, files=files)
            response.raise_for_status()
            logging.info(f"WhatsApp message sent to {phone}: {response.json()}")
    except FileNotFoundError:
        logging.error(f"File not found during WhatsApp sending: {image_path}")
    except Exception as e:
        logging.error(f"Failed to send WhatsApp message to {phone}: {e}")