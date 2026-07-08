# Use Case Diagram - Sistem Ekstraksi Informasi Dokumen Fabrikasi Ducting Berbasis CRF

Dokumen ini menyajikan **Use Case Diagram** untuk sistem aplikasi. Diagram ini mendefinisikan batasan sistem (system boundary), aktor yang terlibat, serta fungsionalitas utama sistem beserta relasi `<<include>>` dan `<<extend>>`.

## Diagram

```mermaid
graph LR
    %% --- STYLE DEFINITIONS ---
    classDef actor fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,font-weight:bold;
    classDef usecase fill:#ffffff,stroke:#4caf50,stroke-width:2px;
    classDef boundary fill:#fcfcfc,stroke:#9e9e9e,stroke-width:2px,stroke-dasharray: 5 5;

    %% --- ACTORS ---
    Admin["👤 Admin (User)"]
    class Admin actor;

    %% --- SYSTEM BOUNDARY ---
    subgraph System ["Sistem Ekstraksi BPD & Material Support"]
        
        %% --- USE CASES ---
        UC_Login(["Login"])
        UC_Logout(["Logout"])

        %% BPD Document UCs
        UC_UploadBPD(["Upload & Ekstraksi BPD"])
        UC_ExtractCRF(["Ekstraksi PDF dengan Model CRF"])
        UC_ShowErrorBPD(["Menampilkan Pesan Error Berkas"])

        UC_KelolaBPD(["Mengelola Data BPD"])
        UC_LihatBPD(["Melihat Detail BPD"])
        UC_CetakBPD(["Mencetak Laporan BPD"])
        UC_HapusBPD(["Menghapus Dokumen BPD"])

        %% Material Support UCs
        UC_KelolaMS(["Mengelola Data Material Support"])
        UC_AddMS(["Tambah Permintaan Material Support"])
        UC_CalcMS(["Kalkulasi Kebutuhan Material"])
        UC_ShowErrorMS(["Menampilkan Pesan Error Input"])
        UC_LihatMS(["Melihat Detail Material Support"])
        UC_CetakMS(["Mencetak Laporan Material Support"])
        UC_HapusMS(["Menghapus Permintaan"])

        %% Assign Use Case Class
        class UC_Login,UC_Logout,UC_UploadBPD,UC_ExtractCRF,UC_ShowErrorBPD,UC_KelolaBPD,UC_LihatBPD,UC_CetakBPD,UC_HapusBPD,UC_KelolaMS,UC_AddMS,UC_CalcMS,UC_ShowErrorMS,UC_LihatMS,UC_CetakMS,UC_HapusMS usecase;
    end
    style System boundary;

    %% --- ACTOR-USE CASE ASSOCIATIONS ---
    Admin --> UC_Login
    Admin --> UC_Logout
    Admin --> UC_UploadBPD
    Admin --> UC_KelolaBPD
    Admin --> UC_KelolaMS

    %% --- INCLUDES (<include>) ---
    UC_UploadBPD -.->|"<<include>>"| UC_ExtractCRF
    UC_AddMS -.->|"<<include>>"| UC_CalcMS

    %% --- EXTENDS (<extend>) ---
    UC_ShowErrorBPD -.->|"<<extend>>"| UC_UploadBPD
    UC_ShowErrorMS -.->|"<<extend>>"| UC_AddMS
    UC_CetakBPD -.->|"<<extend>>"| UC_LihatBPD
    UC_CetakMS -.->|"<<extend>>"| UC_LihatMS

    %% Connect child actions for better visual mapping (Optional / Generalization style)
    UC_KelolaBPD --> UC_LihatBPD
    UC_KelolaBPD --> UC_HapusBPD
    UC_KelolaMS --> UC_AddMS
    UC_KelolaMS --> UC_LihatMS
    UC_KelolaMS --> UC_HapusMS
```

---

## Deskripsi Use Case

### 1. Utama & Autentikasi
- **Login**: Aktor (Admin) masuk ke sistem menggunakan kredensial username dan password untuk mengamankan hak akses.
- **Logout**: Aktor keluar dari sesi sistem untuk mengakhiri akses keamanan.

### 2. Pengelolaan Dokumen BPD
- **Mengelola Data BPD**: Induk use case bagi Admin untuk mencari, memfilter, dan melihat seluruh daftar berkas BPD yang telah tersimpan.
- **Upload & Ekstraksi BPD**: Admin mengunggah berkas PDF BPD untuk dikonversi menjadi data terstruktur.
  - **`<<include>>` Ekstraksi PDF dengan Model CRF**: Sistem secara otomatis memproses klasifikasi teks menggunakan algoritma Conditional Random Fields (CRF).
  - **`<<extend>>` Menampilkan Pesan Error Berkas**: Terjadi jika format berkas yang diunggah tidak valid atau bukan berkas BPD yang dikenali.
- **Melihat Detail BPD**: Admin menampilkan rincian data BPD beserta detail item ducting terdaftar.
  - **`<<extend>>` Mencetak Laporan BPD**: Admin dapat mengekspor atau mencetak hasil laporan BPD dalam bentuk cetakan/PDF dari halaman detail.
- **Menghapus Dokumen BPD**: Admin menghapus data BPD beserta seluruh item ducting yang bersangkutan dari database.

### 3. Pengelolaan Material Support
- **Mengelola Data Material Support**: Induk use case bagi Admin untuk memantau daftar permintaan material support per proyek.
- **Tambah Permintaan Material Support**: Admin membuat pengajuan kebutuhan material support (seperti Corner, Mur Baut, dan Foam Tape) baru dengan memilih referensi dokumen BPD.
  - **`<<include>>` Kalkulasi Kebutuhan Material**: Sistem secara otomatis menghitung estimasi jumlah material support berdasarkan rumus ukuran (W, H, L) dan qty item ducting pada dokumen BPD yang dipilih.
  - **`<<extend>>` Menampilkan Pesan Error Input**: Terjadi jika Admin belum memilih proyek, belum mencentang BPD, atau data tanggal pengiriman kosong saat pengisian form.
- **Melihat Detail Material Support**: Admin menampilkan detail perhitungan metrik kebutuhan material support untuk proyek tertentu.
  - **`<<extend>>` Mencetak Laporan Material Support**: Admin mengunduh / mencetak laporan kebutuhan material support.
- **Menghapus Permintaan**: Admin membatalkan atau menghapus catatan permintaan material support dari database.
