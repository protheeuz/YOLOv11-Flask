import json
import logging
from flask import Blueprint, flash, render_template, redirect, url_for, request, jsonify, current_app, session
from flask_login import login_required, current_user, login_user
from database import get_db
from models import User
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import requests
import os
import mysql.connector

main_bp = Blueprint('main', __name__)

def get_health_check_status(user_id):
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT 
            MAX(heart_rate) AS heart_rate,
            MAX(oxygen_level) AS oxygen_level,
            MAX(temperature) AS temperature,
            MAX(activity_level) AS activity_level,
            MAX(ecg_value) AS ecg_value
        FROM sensor_data
        WHERE user_id = %s AND DATE(timestamp) = CURDATE()
    """, (user_id,))
    health_data = cursor.fetchone()
    cursor.close()

    if health_data is None:
        health_status = {
            'heart_rate': False,
            'oxygen_level': False,
            'temperature': False,
            'activity_level': False,
            'ecg': False
        }
    else:
        health_status = {
            'heart_rate': health_data[0] is not None,
            'oxygen_level': health_data[1] is not None,
            'temperature': health_data[2] is not None,
            'activity_level': health_data[3] is not None,
            'ecg': health_data[4] is not None
        }

    session['health_status'] = health_status
    return health_status

@main_bp.route('/')
@login_required
def index():
    user_id = request.args.get('user_id') or current_user.id
    connection = get_db()
    cursor = connection.cursor()

    if current_user.role == 'admin':
        # Query untuk admin
        cursor.execute("""
            SELECT u.id, u.name, u.registration_date, h.completed 
            FROM users u
            LEFT JOIN health_checks h ON u.id = h.user_id AND h.check_date = CURDATE()
            WHERE u.role='karyawan' AND u.registration_date >= DATE_SUB(NOW(), INTERVAL 2 WEEK)
            ORDER BY u.registration_date DESC
        """)
        recent_users = cursor.fetchall()

        cursor.execute("""
            SELECT 
                DATE(check_date) as date, 
                AVG(completed) as daily_health
            FROM health_checks
            GROUP BY DATE(check_date)
            ORDER BY DATE(check_date) DESC
            LIMIT 30
        """)
        daily_health_data_raw = cursor.fetchall()

        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())

        cursor.execute("""
            SELECT u.name, s.timestamp, h.completed, u.profile_image
            FROM users u
            LEFT JOIN sensor_data s ON u.id = s.user_id
            LEFT JOIN health_checks h ON u.id = h.user_id AND h.check_date = CURDATE()
            WHERE u.role='karyawan' AND DATE(s.timestamp) = CURDATE()
        """)
        today_health_checks = cursor.fetchall()

        cursor.execute("""
            SELECT u.name, s.timestamp, h.completed, u.profile_image
            FROM users u
            LEFT JOIN sensor_data s ON u.id = s.user_id
            LEFT JOIN health_checks h ON u.id = h.user_id AND h.check_date >= %s AND h.check_date <= %s
            WHERE u.role='karyawan' AND DATE(s.timestamp) >= %s AND DATE(s.timestamp) <= %s
        """, (start_of_week, today, start_of_week, today))
        weekly_health_checks = cursor.fetchall()

        cursor.execute("""
            SELECT u.name, s.timestamp, h.completed, u.profile_image
            FROM users u
            LEFT JOIN sensor_data s ON u.id = s.user_id
            LEFT JOIN health_checks h ON u.id = h.user_id
            WHERE u.role='karyawan'
        """)
        all_health_checks = cursor.fetchall()

        cursor.close()

        health_check_labels = [stat[0].strftime('%d %b') for stat in daily_health_data_raw]
        daily_health_data = [stat[1] * 100 for stat in daily_health_data_raw]
        weekly_health_data = []
        monthly_health_data = []

        for i in range(0, len(daily_health_data_raw), 7):
            weekly_avg = sum(d[1] for d in daily_health_data_raw[i:i+7]) / 7 * 100
            weekly_health_data.append(weekly_avg)

        for i in range(0, len(daily_health_data_raw), 30):
            monthly_avg = sum(d[1] for d in daily_health_data_raw[i:i+30]) / 30 * 100
            monthly_health_data.append(monthly_avg)

        return render_template('home/index_admin.html',
                               recent_users=recent_users,
                               health_check_labels=health_check_labels,
                               daily_health_data=daily_health_data,
                               weekly_health_data=weekly_health_data,
                               monthly_health_data=monthly_health_data,
                               today_health_checks=today_health_checks,
                               weekly_health_checks=weekly_health_checks,
                               all_health_checks=all_health_checks)
    else:
        cursor.execute("""
            SELECT completed FROM health_checks
            WHERE user_id = %s AND check_date = CURDATE()
        """, (current_user.id,))
        health_check = cursor.fetchone()

        # Mengambil data terbaru untuk hari ini atau data terbaru yang tersedia
        cursor.execute("""
            SELECT 
                COALESCE(MAX(CASE WHEN DATE(timestamp) = CURDATE() THEN heart_rate ELSE NULL END), 
                         MAX(heart_rate)) AS heart_rate,
                COALESCE(MAX(CASE WHEN DATE(timestamp) = CURDATE() THEN oxygen_level ELSE NULL END), 
                         MAX(oxygen_level)) AS oxygen_level,
                COALESCE(MAX(CASE WHEN DATE(timestamp) = CURDATE() THEN temperature ELSE NULL END), 
                         MAX(temperature)) AS temperature,
                COALESCE(MAX(CASE WHEN DATE(timestamp) = CURDATE() THEN activity_level ELSE NULL END), 
                         MAX(activity_level)) AS activity_level
            FROM sensor_data
            WHERE user_id = %s
        """, (current_user.id,))
        latest_health_data = cursor.fetchone()

        cursor.execute("""
            SELECT ecg_value, timestamp 
            FROM sensor_data
            WHERE user_id = %s AND ecg_value IS NOT NULL
            ORDER BY timestamp DESC
        """, (current_user.id,))
        ecg_data = cursor.fetchall()

        cursor.close()

        # Penanganan data jika tidak ditemukan
        if latest_health_data is None or all(v is None for v in latest_health_data):
            latest_health_data = {
                'heart_rate': '-',
                'oxygen_level': '-',
                'temperature': '-',
                'activity_level': '-'
            }
        else:
            latest_health_data = {
                'heart_rate': latest_health_data[0] if latest_health_data[0] is not None else '-',
                'oxygen_level': latest_health_data[1] if latest_health_data[1] is not None else '-',
                'temperature': latest_health_data[2] if latest_health_data[2] is not None else '-',
                'activity_level': latest_health_data[3] if latest_health_data[3] is not None else '-'
            }

        # Memecah JSON ecg_value ke dalam list
        ecg_values = []
        ecg_timestamps = []
        for ecg_record in ecg_data:
            values = json.loads(ecg_record[0])  # Load JSON data
            timestamp = ecg_record[1].strftime('%H:%M:%S')
            ecg_values.extend(values)  # Add all values to the list
            ecg_timestamps.extend([timestamp] * len(values))  # Repeat timestamp for each value

        health_status = get_health_check_status(current_user.id)

        return render_template('home/index_karyawan.html',
                               latest_health_data=latest_health_data,
                               ecg_values=ecg_values,
                               ecg_timestamps=ecg_timestamps,
                               health_status=health_status)

@main_bp.route('/index_karyawan')
@login_required
def index_karyawan():
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT completed FROM health_checks
        WHERE user_id = %s AND check_date = CURDATE()
    """, (current_user.id,))
    health_check = cursor.fetchone()
    
    # Mengambil data terbaru untuk hari ini atau data terbaru yang tersedia
    cursor.execute("""
        SELECT 
            COALESCE(MAX(CASE WHEN DATE(timestamp) = CURDATE() THEN heart_rate ELSE NULL END), 
                     MAX(heart_rate)) AS heart_rate,
            COALESCE(MAX(CASE WHEN DATE(timestamp) = CURDATE() THEN oxygen_level ELSE NULL END), 
                     MAX(oxygen_level)) AS oxygen_level,
            COALESCE(MAX(CASE WHEN DATE(timestamp) = CURDATE() THEN temperature ELSE NULL END), 
                     MAX(temperature)) AS temperature,
            COALESCE(MAX(CASE WHEN DATE(timestamp) = CURDATE() THEN activity_level ELSE NULL END), 
                     MAX(activity_level)) AS activity_level
        FROM sensor_data
        WHERE user_id = %s
    """, (current_user.id,))
    latest_health_data = cursor.fetchone()

    cursor.execute("""
        SELECT ecg_value, timestamp 
        FROM sensor_data
        WHERE user_id = %s AND ecg_value IS NOT NULL
        ORDER BY timestamp DESC
    """, (current_user.id,))
    ecg_data = cursor.fetchall()

    cursor.close()

    # Penanganan data jika tidak ditemukan
    if latest_health_data is None or all(v is None for v in latest_health_data):
        latest_health_data = {
            'heart_rate': '-',
            'oxygen_level': '-',
            'temperature': '-',
            'activity_level': '-'
        }
    else:
        latest_health_data = {
            'heart_rate': latest_health_data[0] if latest_health_data[0] is not None else '-',
            'oxygen_level': latest_health_data[1] if latest_health_data[1] is not None else '-',
            'temperature': latest_health_data[2] if latest_health_data[2] is not None else '-',
            'activity_level': latest_health_data[3] if latest_health_data[3] is not None else '-'
        }

    ecg_values = [data[0] for data in ecg_data]
    ecg_timestamps = [data[1].strftime('%H:%M:%S') for data in ecg_data]

    health_status = get_health_check_status(current_user.id)

    return render_template('home/index_karyawan.html',
                           latest_health_data=latest_health_data,
                           ecg_values=ecg_values,
                           ecg_timestamps=ecg_timestamps,
                           health_status=health_status)

@main_bp.route('/skip_health_check', methods=['POST'])
@login_required
def skip_health_check():
    return jsonify({"status": "sukses", "redirect": url_for('main.index_karyawan')})

@main_bp.route('/notifications')
@login_required
def notifications():
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    new_notifications = get_new_logins_for_admin()
    old_notifications = get_old_logins_for_admin()
    new_logins_count = len(new_notifications)

    return render_template('includes/navigation.html',
                           new_notifications=new_notifications,
                           old_notifications=old_notifications,
                           new_logins_count=new_logins_count)

def get_new_logins_for_admin():
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT name, last_login, TIMESTAMPDIFF(MINUTE, last_login, NOW()) as time_ago
        FROM users
        WHERE last_login >= CURDATE()
        ORDER BY last_login DESC
    """)
    logins = cursor.fetchall()
    cursor.close()
    return [{'user_name': login[0], 'time_ago': f'{login[2]} min', 'message': 'Baru login'} for login in logins]

def get_old_logins_for_admin():
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT name, last_login, TIMESTAMPDIFF(MINUTE, last_login, NOW()) as time_ago
        FROM users
        WHERE last_login < CURDATE()
        ORDER BY last_login DESC
    """)
    logins = cursor.fetchall()
    cursor.close()
    return [{'user_name': login[0], 'time_ago': f'{login[2]} min', 'message': 'Login sebelumnya'} for login in logins]

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
    health_status = get_health_check_status(current_user.id) or {}
    return render_template('health_check_modal.html', health_status=health_status)

@main_bp.route('/get_sensor_data/<sensor>', methods=['GET'])
@login_required
def get_sensor_data(sensor):
    try:
        esp32_ip = '192.168.20.184'
        response = requests.get(f'http://{esp32_ip}/get_sensor_data/{sensor}')
        data = response.json()
        if response.status_code == 200:
            return jsonify({'status': 'sukses', 'value': data})
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
    ecg_values = data.get('ecg_value')

    if user_id == 0 or user_id is None:
        current_app.logger.error("Invalid user_id received.")
        return jsonify({"status": "gagal", "message": "Invalid user_id"}), 400

    connection = get_db()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO sensor_data (user_id, heart_rate, oxygen_level, temperature, activity_level, ecg_value)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, heart_rate, oxygen_level, temperature, activity_level, ecg_values))

        connection.commit()

        cursor.execute("""
            SELECT 
                MAX(CASE WHEN heart_rate IS NOT NULL THEN 1 ELSE 0 END) AS heart_rate_filled,
                MAX(CASE WHEN oxygen_level IS NOT NULL THEN 1 ELSE 0 END) AS oxygen_level_filled,
                MAX(CASE WHEN temperature IS NOT NULL THEN 1 ELSE 0 END) AS temperature_filled,
                MAX(CASE WHEN activity_level IS NOT NULL THEN 1 ELSE 0 END) AS activity_level_filled,
                MAX(CASE WHEN ecg_value IS NOT NULL THEN 1 ELSE 0 END) AS ecg_filled
            FROM sensor_data
            WHERE user_id = %s
        """, (user_id,))
        sensor_status = cursor.fetchone()

        if all(sensor_status):
            check_date = datetime.now().date()
            cursor.execute("""
                INSERT INTO health_checks (user_id, check_date, completed)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE completed = 1
            """, (user_id, check_date, 1))
            connection.commit()

            return jsonify({"status": "sukses", "redirect": url_for('main.index_karyawan')})

        return jsonify({"status": "sukses"})
    except mysql.connector.errors.IntegrityError as e:
        connection.rollback()
        current_app.logger.error(f"Database error: {e}")
        return jsonify({"status": "gagal", "message": str(e)}), 500
    finally:
        cursor.close()

@main_bp.route('/request_sensor_data', methods=['POST'])
@login_required
def request_sensor_data():
    esp32_ip = request.json.get('esp32_ip')
    sensor = request.json.get('sensor')
    user_id = current_user.id

    current_app.logger.debug(f"Requesting sensor data for sensor: {sensor}")

    try:
        response = requests.get(f'http://{esp32_ip}/get_sensor_data/{sensor}')
        current_app.logger.debug(f"Response from ESP32: {response.status_code}, {response.text}")

        try:
            data = response.json()
        except ValueError:
            current_app.logger.error(f"Invalid JSON received: {response.text}")
            return jsonify({'status': 'gagal', 'message': 'Invalid JSON received from ESP32'}), 500

        if response.status_code == 200:
            if 'user_id' in data and data['user_id'] != user_id:
                current_app.logger.error("Invalid user_id received.")
                return jsonify({'status': 'gagal', 'message': 'Invalid user_id'}), 400

            connection = get_db()
            cursor = connection.cursor()

            if sensor == 'ecg':
                if isinstance(data.get('value'), list):
                    ecg_values_json = json.dumps(data['value'])

                    cursor.execute("""
                        INSERT INTO sensor_data (user_id, ecg_value)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE ecg_value = %s
                    """, (user_id, ecg_values_json, ecg_values_json))
                    connection.commit()

            else:
                sensor_value = data.get('value')
                if sensor in ['heart_rate', 'oxygen_level', 'temperature', 'activity_level'] and sensor_value is not None:
                    cursor.execute(f"""
                        INSERT INTO sensor_data (user_id, {sensor})
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE {sensor} = %s
                    """, (user_id, sensor_value, sensor_value))
                    connection.commit()

            cursor.execute("""
                SELECT heart_rate, oxygen_level, temperature, activity_level, ecg_value
                FROM sensor_data
                WHERE user_id = %s AND DATE(timestamp) = CURDATE()
                ORDER BY timestamp DESC LIMIT 1
            """, (user_id,))
            health_data = cursor.fetchone()

            if all(health_data):
                cursor.execute("""
                    INSERT INTO health_checks (user_id, check_date, completed)
                    VALUES (%s, CURDATE(), 1)
                    ON DUPLICATE KEY UPDATE completed = 1
                """, (user_id,))
                connection.commit()

                cursor.close()
                return jsonify({'status': 'sukses', 'redirect': url_for('main.index_karyawan')})

            cursor.close()
            return jsonify({'status': 'sukses', 'message': f'Data {sensor.capitalize()} berhasil disimpan'})

        return jsonify({'status': 'gagal', 'message': 'ESP32 tidak merespons dengan benar'}), 400

    except Exception as e:
        current_app.logger.error(f"Error processing sensor data: {str(e)}")
        return jsonify({'status': 'gagal', 'message': str(e)}), 500

@main_bp.route('/poll_health_check_status', methods=['GET'])
def poll_health_check_status():
    session_token = request.headers.get('Session-Token')
    user_id = session.get('user_id')
    current_app.logger.debug(f'Polling health check status, session user_id: {user_id}, session_token: {session_token}')
    if session_token and session_token == session.get('session_token'):
        return jsonify({"user_id": user_id})
    else:
        return jsonify({"user_id": -1})

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

@main_bp.route('/employee_list')
@login_required
def employee_list():
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT nik, name, registration_date, last_login, address, about, id  # Tambahkan id di sini
        FROM users
        WHERE role = 'karyawan'
        ORDER BY registration_date DESC
    """)
    employees = cursor.fetchall()

    cursor.close()

    return render_template('home/employee_list.html', employees=employees)

@main_bp.route('/auth/send_user_id', methods=['POST'])
@login_required
def send_user_id():
    user_id = request.json.get('user_id')
    esp32_ip = request.json.get('esp32_ip')

    if not user_id or not esp32_ip:
        return jsonify({'status': 'gagal', 'message': 'Invalid user_id or esp32_ip'})

    try:
        response = requests.post(f'http://{esp32_ip}/set_user_id', json={'user_id': user_id})
        if response.status_code == 200:
            return jsonify({'status': 'sukses'})
        else:
            return jsonify({'status': 'gagal', 'message': 'Failed to send User ID to ESP32'})
    except Exception as e:
        return jsonify({'status': 'gagal', 'message': str(e)}), 500

@main_bp.route('/auth/send_session_token', methods=['POST'])
@login_required
def send_session_token():
    session_token = request.json.get('session_token')
    esp32_ip = request.json.get('esp32_ip')

    if not session_token or not esp32_ip:
        return jsonify({'status': 'gagal', 'message': 'Invalid session_token or esp32_ip'})

    try:
        response = requests.post(f'http://{esp32_ip}/set_session_token', json={'session_token': session_token})
        if response.status_code == 200:
            return jsonify({'status': 'sukses'})
        else:
            return jsonify({'status': 'gagal', 'message': 'Failed to send Session Token to ESP32'})
    except Exception as e:
        return jsonify({'status': 'gagal', 'message': str(e)}), 500

@main_bp.route('/riwayat')
@login_required
def riwayat():
    connection = get_db()
    cursor = connection.cursor()

    # Mengambil data riwayat sensor untuk semua karyawan
    cursor.execute("""
        SELECT u.name, DATE(s.timestamp) as date, 
               MAX(s.heart_rate) AS heart_rate, 
               MAX(s.oxygen_level) AS oxygen_level, 
               MAX(s.temperature) AS temperature, 
               MAX(s.activity_level) AS activity_level
        FROM sensor_data s
        JOIN users u ON s.user_id = u.id
        WHERE u.role = 'karyawan'
        GROUP BY u.name, DATE(s.timestamp)
        ORDER BY DATE(s.timestamp) DESC
    """)
    riwayat_data = cursor.fetchall()

    # Mengambil data ECG untuk semua karyawan
    cursor.execute("""
        SELECT u.name, s.ecg_value, DATE(s.timestamp) as date, s.timestamp
        FROM sensor_data s
        JOIN users u ON s.user_id = u.id
        WHERE u.role = 'karyawan' AND s.ecg_value IS NOT NULL
        ORDER BY s.timestamp ASC
    """)
    ecg_data = cursor.fetchall()
    cursor.close()

    ecg_data_by_date = {}
    for ecg_record in ecg_data:
        name = ecg_record[0]
        date = ecg_record[2].strftime('%Y-%m-%d')
        if date not in ecg_data_by_date:
            ecg_data_by_date[date] = {'name': name, 'values': [], 'timestamps': []}

        values = json.loads(ecg_record[1])
        timestamp = ecg_record[3].strftime('%H:%M:%S')
        ecg_data_by_date[date]['values'].extend(values)
        ecg_data_by_date[date]['timestamps'].extend([timestamp] * len(values))

    # Menggabungkan data riwayat sensor dan ECG
    riwayat_data_by_date = {}
    for row in riwayat_data:
        name = row[0]
        date = row[1].strftime('%Y-%m-%d')
        if date not in riwayat_data_by_date:
            riwayat_data_by_date[date] = {
                'name': name,
                'heart_rate': row[2] if row[2] else '-',
                'oxygen_level': row[3] if row[3] else '-',
                'temperature': row[4] if row[4] else '-',
                'activity_level': row[5] if row[5] else '-',
                'ecg_values': [],
                'ecg_timestamps': []
            }

        # Jika ada data ECG, tambahkan ke data riwayat
        if date in ecg_data_by_date:
            riwayat_data_by_date[date]['ecg_values'] = ecg_data_by_date[date]['values']
            riwayat_data_by_date[date]['ecg_timestamps'] = ecg_data_by_date[date]['timestamps']

    return render_template('home/riwayat.html', riwayat_data=riwayat_data_by_date)

@main_bp.route('/riwayat_karyawan/<int:user_id>')
@login_required
def riwayat_karyawan(user_id):
    if current_user.id != user_id and current_user.role != 'admin':
        return redirect(url_for('main.index'))

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT DATE(timestamp) as date, 
               MAX(heart_rate) AS heart_rate, 
               MAX(oxygen_level) AS oxygen_level, 
               MAX(temperature) AS temperature, 
               MAX(activity_level) AS activity_level
        FROM sensor_data
        WHERE user_id = %s
        GROUP BY DATE(timestamp)
        ORDER BY DATE(timestamp) DESC
    """, (user_id,))
    riwayat_data = cursor.fetchall()

    cursor.execute("""
        SELECT ecg_value, DATE(timestamp) as date
        FROM sensor_data
        WHERE user_id = %s AND ecg_value IS NOT NULL
        ORDER BY timestamp ASC
    """, (user_id,))
    ecg_data = cursor.fetchall()
    cursor.close()

    ecg_data_by_date = {}
    for ecg_record in ecg_data:
        date = ecg_record[1].strftime('%Y-%m-%d')
        if date not in ecg_data_by_date:
            ecg_data_by_date[date] = {'values': [], 'timestamps': []}

        values = json.loads(ecg_record[0])
        timestamp = ecg_record[1].strftime('%H:%M:%S')
        ecg_data_by_date[date]['values'].extend(values)
        ecg_data_by_date[date]['timestamps'].extend([timestamp] * len(values))

    return render_template('home/riwayat_karyawan.html', 
                           riwayat_data=riwayat_data, 
                           ecg_data_by_date=ecg_data_by_date)