## Penjelasan Kode

### Endpoint /register:
```Endpoint /register: Menyimpan data pengguna baru dan encoding wajah mereka.```
### Endpoint /login:
```Endpoint /login: Mengautentikasi pengguna dengan NIK dan password, memeriksa status pengecekan kesehatan, dan mengarahkan pengguna ke halaman pengecekan kesehatan jika belum selesai.```
### Endpoint /login_face:
```Endpoint /login_face: Mengautentikasi pengguna dengan pengenalan wajah, memeriksa status pengecekan kesehatan, dan mengarahkan pengguna ke halaman pengecekan kesehatan jika belum selesai.```
### Endpoint /generate_qr
```Endpoint /generate_qr: Menghasilkan QR code berdasarkan NIK pengguna.```
### Endpoint /login_qr
```Endpoint /login_qr: Mengautentikasi pengguna dengan QR code, memeriksa status pengecekan kesehatan, dan mengarahkan pengguna ke halaman pengecekan kesehatan jika belum selesai.```
### Endpoint /sensor_data
```Endpoint /sensor_data: Menerima data sensor dari ESP32, menyimpannya dalam tabel sensor_data, dan menandai pengecekan kesehatan sebagai selesai untuk hari itu.```
### Endpoint /dashboard<int:user_id>
```Endpoint /dashboard/<int:user_id>: Menampilkan halaman dashboard setelah pengecekan kesehatan selesai.```
### Endpoint /health_check/<int:user_id>
```Endpoint /health_check/<int:user_id>: Menampilkan halaman pengecekan kesehatan jika belum selesai.```