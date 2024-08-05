## Penjelasan Kode

### Endpoint `/register`
**Deskripsi:**
Menyimpan data pengguna baru dan encoding wajah mereka.

### Endpoint `/login`
**Deskripsi:**
Mengautentikasi pengguna dengan NIK dan password, memeriksa status pengecekan kesehatan, dan mengarahkan pengguna ke halaman pengecekan kesehatan jika belum selesai.

### Endpoint `/login_face`
**Deskripsi:**
Mengautentikasi pengguna dengan pengenalan wajah, memeriksa status pengecekan kesehatan, dan mengarahkan pengguna ke halaman pengecekan kesehatan jika belum selesai.

### Endpoint `/generate_qr`
**Deskripsi:**
Menghasilkan QR code berdasarkan NIK pengguna.

### Endpoint `/login_qr`
**Deskripsi:**
Mengautentikasi pengguna dengan QR code, memeriksa status pengecekan kesehatan, dan mengarahkan pengguna ke halaman pengecekan kesehatan jika belum selesai.

### Endpoint `/sensor_data`
**Deskripsi:**
Menerima data sensor dari ESP32, menyimpannya dalam tabel `sensor_data`, dan menandai pengecekan kesehatan sebagai selesai untuk hari itu.

### Endpoint `/dashboard/<int:user_id>`
**Deskripsi:**
Mengalihkan pengguna ke halaman dashboard setelah pengecekan kesehatan selesai.

### Endpoint `/health_check`
**Deskripsi:**
Menampilkan status pengecekan kesehatan untuk pengguna yang sedang login.

### Endpoint `/health_check_modal`
**Deskripsi:**
Menampilkan modal untuk pengecekan kesehatan.

### Endpoint `/get_sensor_data/<sensor>`
**Deskripsi:**
Mengambil data sensor dari ESP32.

### Endpoint `/request_sensor_data`
**Deskripsi:**
Mengirim permintaan data sensor ke ESP32.

### Endpoint `/poll_health_check_status`
**Deskripsi:**
Memeriksa status pengecekan kesehatan pengguna.

### Endpoint `/profile`
**Deskripsi:**
Menampilkan halaman profil pengguna.

### Endpoint `/update_profile`
**Deskripsi:**
Memperbarui data profil pengguna.

### Endpoint `/update_profile_image`
**Deskripsi:**
Mengunggah dan memperbarui foto profil pengguna.

### Endpoint `/notifications`
**Deskripsi:**
Menampilkan notifikasi untuk admin tentang login terbaru.

### Endpoint `/`
**Deskripsi:**
Menampilkan halaman utama dashboard. Halaman ini berbeda untuk admin dan karyawan:
- **Admin:** Menampilkan daftar pengguna terbaru dan statistik pengecekan kesehatan harian, mingguan, dan bulanan.
- **Karyawan:** Menampilkan data kesehatan terbaru dan grafik ECG.