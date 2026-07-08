# Class Diagram - Sistem Ekstraksi Informasi Dokumen Fabrikasi Ducting Berbasis CRF

Dokumen ini berisi Class Diagram sistem yang disesuaikan dengan pola arsitektur yang Anda berikan, mencakup entitas data (dengan method CRUD standar) serta komponen pemrosesan ekstraksi CRF dan pelaporan.

```mermaid
classDiagram
    %% --- ENTITAS DATA ---
    class User {
        +id_user : int
        +username : string
        +password : string
        +login() : bool
        +getUser() : object
    }

    class BpdDocument {
        +id : int
        +project_name : string
        +bpd_no : string
        +lantai : string
        +unit_area : string
        +bpd_date : date
        +getAll() : array
        +insert() : bool
        +delete() : bool
        +find() : object
    }

    class BpdItem {
        +id : int
        +document_id : int
        +nama_ducting : string
        +join_type : string
        +w : string
        +h : string
        +l : string
        +bjls : string
        +qty : int
        +kebutuhan_material : float
        +getAll() : array
        +insert() : bool
        +delete() : bool
    }

    class MaterialSupport {
        +id : int
        +request_no : string
        +project_name : string
        +bpd_ids : string
        +bpd_nos : string
        +corner : int
        +mur_baut : int
        +foam_tape : int
        +getAll() : array
        +insert() : bool
        +delete() : bool
    }

    %% --- SERVICE & LAPORAN ---
    class CrfService {
        +tokenizePdf(file) : array
        +word2features(sent, i) : array
        +predictTags(sentences) : array
        +groupEntities(sentences, tags) : array
        +proses() : array
    }

    class Laporan {
        +id : int
        +jenis_laporan : string
        +tanggal : datetime
        +laporanBPD() : array
        +laporanMaterial() : array
        +cetakPDF() : void
    }

    %% --- HUBUNGAN & RELASI ---
    User "1" --> "*" BpdDocument : "mengelola"
    BpdDocument "1" *-- "*" BpdItem : "berisi"
    MaterialSupport "*" --> "1" BpdDocument : "merujuk"

    CrfService ..> BpdDocument : "<<create>>"
    CrfService ..> BpdItem : "<<create>>"

    Laporan ..> BpdDocument : "<<use>>"
    Laporan ..> MaterialSupport : "<<use>>"
```

---

## Deskripsi Relasi
- **User** ke **BpdDocument (`1` ke `*`)**: Satu user dapat mengelola atau mengunggah banyak dokumen BPD (Directed Association).
- **BpdDocument** ke **BpdItem (`1` ke `*`)**: Satu dokumen BPD terdiri atas banyak item detail ducting (Composition).
- **MaterialSupport** ke **BpdDocument (`*` ke `1`)**: Satu atau beberapa pengajuan material support merujuk pada dokumen BPD yang bersangkutan (Directed Association).
- **CrfService** ke **BpdDocument / BpdItem (`<<create>>`)**: Layanan ekstraksi CRF bertugas untuk memproses PDF dan menginstansiasi/membuat (`create`) entitas data BPD & BpdItem baru (Dependency).
- **Laporan** ke **Entitas (`<<use>>`)**: Kelas laporan menggunakan (`use`) data BPD dan Material Support untuk digenerate menjadi bentuk PDF/cetak (Dependency).
