import json
import logging
from flask import Blueprint, flash, render_template, redirect, url_for, request, jsonify, current_app, session
from flask_login import login_required, current_user, login_user
from database import get_db
from models import User
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    user_id = request.args.get('user_id') or current_user.id
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, registration_date
        FROM users
        WHERE registration_date >= DATE_SUB(NOW(), INTERVAL 2 WEEK)
        ORDER BY registration_date DESC
    """)
    recent_users = cursor.fetchall()

    cursor.close()

    return render_template('home/index_admin.html', recent_users=recent_users)

@main_bp.route('/profile')
@login_required
def profile():
    return render_template('home/profile.html')

@main_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    # Mengambil data dari form
    name = request.form['name']
    address = request.form['address']
    about = request.form['about']
    phone = request.form.get('phone')  # Mengambil nomor telepon (baru)

    # Membuka koneksi ke database
    connection = get_db()
    cursor = connection.cursor()

    # Update query untuk menyertakan kolom phone
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

@main_bp.route('/notifications')
@login_required
def notifications():
    return jsonify({"error": "Unauthorized"}), 403

@main_bp.route('/dashboard/<int:user_id>')
@login_required
def dashboard(user_id):
    return redirect(url_for('main.index'))

@main_bp.route('/riwayat/<int:user_id>')
def riwayat(user_id):
    return render_template('home/riwayat.html', user_id=user_id)