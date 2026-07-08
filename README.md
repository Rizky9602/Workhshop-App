# Sistem Ekstraksi Informasi Dokumen Fabrikasi Ducting Berbasis CRF

Aplikasi berbasis web menggunakan Flask untuk digitalisasi dan ekstraksi informasi otomatis dari dokumen BPD (Bukti Permintaan Ducting) menggunakan metode **Conditional Random Fields (CRF)**. Sistem ini membantu mengotomatiskan pembacaan dokumen PDF hasil fabrikasi ducting, memverifikasi datanya, serta menghitung kebutuhan material utama dan material support secara cepat dan efisien.

---

## 🚀 Fitur Utama

1. **Dashboard & Statistik Real-time**:
   * Menampilkan tren verifikasi dokumen BPD bulanan (visualisasi bar chart).
   * Grafik persentase penggunaan ketebalan BJLS (visualisasi doughnut chart).
   * Statistik proyek aktif dan total BPD bulan ini.

2. **Ekstraksi Informasi PDF otomatis (CRF)**:
   * Mengunggah berkas PDF dokumen BPD.
   * Melakukan tokenisasi dokumen menggunakan `pdfplumber`.
   * Klasifikasi token menggunakan model mesin pembelajaran CRF (`model_crf.pkl`) untuk mengenali entitas penting seperti Nama Proyek, Nomor BPD, Lantai, Unit/Area, Item Ducting, Ukuran (W, H, L), Sambungan (Join), Ketebalan (BJLS), dan Jumlah (Qty).

3. **Verifikasi & Penyimpanan Data**:
   * Antarmuka interaktif untuk memeriksa dan menyunting data hasil ekstraksi sebelum disimpan ke database MySQL.
   * Validasi kesalahan input otomatis.

4. **Kalkulasi Kebutuhan Material**:
   * Perhitungan otomatis kebutuhan lembaran BJLS berdasarkan kategori ducting (Kategori A: Lurus/Elbow/Reducer dll., atau Kategori B: Cabang TY/Tee/Cross dll.).
   * Mendukung sambungan TFD (Transverse Flange Duct) dan Sisip/Slip.

5. **Kalkulasi & Rekapitulasi Material Support**:
   * Perhitungan otomatis komponen pendukung sambungan tipe TFD seperti:
     * **Corner** (Pojokan)
     * **Mur Baut**
     * **Foam Tape** (Gasket foam tape)
   * Menyimpan dan merekap permintaan material support per proyek.

6. **Laporan & Pencetakan**:
   * Cetak bukti permintaan ducting dan laporan perhitungan material support.
   * Laporan bulanan pemakaian BJLS per ketebalan dan rekapitulasi komponen support.

---

## 🛠️ Teknologi yang Digunakan

* **Backend**: Python 3, Flask, PyMySQL
* **Pengolahan Dokumen & NLP**: pdfplumber, CRF (Conditional Random Fields via Python pickle)
* **Frontend**: HTML5, Vanilla CSS, Vanilla JavaScript, Bootstrap 5, Chart.js, Bootstrap Icons
* **Database**: MySQL

---

## ⚙️ Cara Instalasi dan Menjalankan Aplikasi

### 1. Prasyarat
* Python 3.8 ke atas terinstal di sistem Anda.
* MySQL Server aktif.

### 2. Instalasi Dependensi
Buka terminal/command prompt di direktori proyek dan instal pustaka Python yang diperlukan:
```bash
pip install flask pymysql pdfplumber sklearn-crfsuite
```
*Catatan: Pastikan Anda juga memiliki file model CRF terlatih bernama `model_crf.pkl` di dalam folder `models/`.*

### 3. Konfigurasi Database
Buat database bernama `workshop_db` di MySQL Anda dan jalankan skema tabel untuk `users`, `bpd_documents`, `bpd_items`, dan `material_supports`.

Atur variabel lingkungan (Environment Variables) jika diperlukan (default localhost):
* `DB_HOST` (default: `localhost`)
* `DB_USER` (default: `root`)
* `DB_PASSWORD` (default: `rizky09`)
* `DB_NAME` (default: `workshop_db`)
* `SECRET_KEY` (kunci enkripsi sesi Flask)

### 4. Jalankan Aplikasi
Jalankan perintah berikut di direktori utama proyek:
```bash
python app.py
```
Setelah aplikasi berjalan, buka peramban (browser) dan akses alamat:
`http://127.0.0.1:5000/`

---

## 📁 Struktur Direktori Proyek

```text
├── models/
│   └── model_crf.pkl        # File model CRF yang sudah dilatih
├── uploads/                 # Tempat penyimpanan sementara PDF yang diunggah
├── templates/               # Berisi semua file template HTML (Jinja2)
│   ├── index.html           # Halaman Dashboard utama
│   ├── Upload.html          # Halaman unggah PDF dan verifikasi data
│   ├── bpd_management.html  # Halaman manajemen dokumen BPD
│   └── ...                  # Template laporan dan detail lainnya
├── static/
│   ├── css/
│   │   └── style.css        # Berkas styling CSS terpusat
│   └── js/
│       ├── script.js        # JavaScript untuk navigasi & grafik dashboard
│       └── scan_verify.js   # JavaScript untuk alur upload & tabel verifikasi
├── app.py                   # Aplikasi Flask utama (Backend & API Routes)
└── README.md                # Dokumentasi aplikasi ini
```
