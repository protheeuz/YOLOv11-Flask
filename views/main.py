from flask import Blueprint, flash, render_template, redirect, url_for, request, jsonify, current_app, session
from flask_login import login_required, current_user, login_user
from database import get_db
from models import User
from datetime import datetime
from werkzeug.utils import secure_filename
import requests
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    user_id = request.args.get('user_id')
    connection = get_db()
    cursor = connection.cursor()
    
    cursor.execute("""
        SELECT u.id, u.name, u.registration_date, h.completed 
        FROM users u
        LEFT JOIN health_checks h ON u.id = h.user_id AND h.check_date = CURDATE()
        WHERE u.role='karyawan' AND u.registration_date >= DATE_SUB(NOW(), INTERVAL 2 WEEK)
        ORDER BY u.registration_date DESC
    """)
    recent_users = cursor.fetchall()
    
    cursor.close()
    return render_template('home/index.html', recent_users=recent_users, user_id=user_id)


@main_bp.route('/dashboard/<int:user_id>')
@login_required
def dashboard(user_id):
    return redirect(url_for('main.index'))

@main_bp.route('/health_check')
@login_required
def health_check():
    user_id = current_user.id
    connection = get_db()
    cursor = connection.cursor()
    
    cursor.execute("""
        SELECT completed 
        FROM health_checks 
        WHERE user_id = %s AND check_date = CURDATE()
    """, (user_id,))
    health_check = cursor.fetchone()
    
    cursor.close()
    return jsonify({'health_check_completed': health_check and health_check[0]})

@main_bp.route('/health_check_modal')
@login_required
def health_check_modal():
    return render_template('health_check_modal.html')

@main_bp.route('/get_sensor_data/<sensor>', methods=['GET'])
@login_required
def get_sensor_data(sensor):
    try:
        esp32_ip = '192.168.20.184'
        response = requests.get(f'http://{esp32_ip}/sensor_data/{sensor}')
        data = response.json()
        if response.status_code == 200:
            return jsonify({'status': 'sukses', 'value': data['value']})
        else:
            return jsonify({'status': 'gagal', 'message': data['message']}), 400
    except Exception as e:
        return jsonify({'status': 'gagal', 'message': str(e)}), 500


@main_bp.route('/sensor_data', methods=['POST'])
def sensor_data():
    data = request.get_json()
    user_id = data.get('user_id')
    heart_rate = data.get('heart_rate')
    oxygen_level = data.get('oxygen_level')
    temperature = data.get('temperature')
    activity_level = data.get('activity_level')
    ecg_value = data.get('ecg_value')
    
    connection = get_db()
    cursor = connection.cursor()
    
    current_app.logger.info(f"user_id: {user_id}, heart_rate: {heart_rate}, oxygen_level: {oxygen_level}, temperature: {temperature}, activity_level: {activity_level}, ecg_value: {ecg_value}")
    
    cursor.execute("""
        INSERT INTO sensor_data (user_id, heart_rate, oxygen_level, temperature, activity_level, ecg_value)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, heart_rate, oxygen_level, temperature, activity_level, ecg_value))
    
    check_date = datetime.now().date()
    cursor.execute("UPDATE health_checks SET completed = TRUE WHERE user_id = %s AND check_date = %s", (user_id, check_date))
    connection.commit()
    cursor.close()

    return jsonify({"status": "sukses"})


@main_bp.route('/poll_health_check_status', methods=['GET'])
def poll_health_check_status():
    user_id = session.get('user_id')
    session_token = session.get('session_token')
    current_app.logger.debug(f'Polling health check status, session user_id: {user_id}, session_token: {session_token}')
    if user_id and session_token:
        return jsonify({"user_id": user_id, "session_token": session_token})
    else:
        return jsonify({"user_id": -1, "session_token": None})

@main_bp.route('/profile')
@login_required
def profile():
    return render_template('home/profile.html')

def save_profile_image(image_file):
    filename = secure_filename(image_file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    image_file.save(filepath)
    return 'uploads/' + filename

@main_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    name = request.form['name']
    address = request.form['address']
    about = request.form['about']
    
    connection = get_db()
    cursor = connection.cursor()
    
    cursor.execute("""
        UPDATE users
        SET name = %s, address = %s, about = %s
        WHERE id = %s
    """, (name, address, about, current_user.id))
    
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
    if (profile_image):
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