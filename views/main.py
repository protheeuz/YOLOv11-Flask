from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    return render_template('index.html')

@main_bp.route('/dashboard/<int:user_id>')
@login_required
def dashboard(user_id):
    return f"Selamat datang di dashboard, user {user_id}!"

@main_bp.route('/health_check/<int:user_id>')
@login_required
def health_check(user_id):
    return f"Silakan selesaikan pengecekan kesehatan Anda, user {user_id}!"

@main_bp.route('/sensor_data', methods=['POST'])
def sensor_data():
    # Ambil data dari form sensor
    user_id = request.form['user_id']
    heart_rate = request.form['heart_rate']
    oxygen_level = request.form['oxygen_level']
    temperature = request.form['temperature']
    activity_level = request.form['activity_level']
    
    # Simpan data sensor ke database
    connection = get_db()
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

    return jsonify({"status": "sukses"})