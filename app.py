from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os
import pdfplumber
import joblib
import datetime

# --- KONFIGURASI APLIKASI ---
app = Flask(__name__)
app.secret_key = 'key' # Kunci pengaman sesi
UPLOAD_FOLDER = 'static/uploads'
MODEL_PATH = 'model_ducting.pkl'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Pastikan folder upload ada
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- BAGIAN 1: LOGIKA AI (Feature Extraction) ---
# Fungsi ini WAJIB SAMA PERSIS dengan saat training
def word2features(sent, i):
    word = str(sent[i])
    features = {
        'bias': 1.0,
        'word.lower()': word.lower(),
        'word.isupper()': word.isupper(),
        'word.isdigit()': word.isdigit(),
        'has_x': 'x' in word.lower(),
        'has_slash': '/' in word,
        'is_p_or_s': word.lower() in ['p', 's'],
    }
    if i > 0:
        word1 = str(sent[i-1])
        features.update({'-1:word.lower()': word1.lower(), '-1:word.isdigit()': word1.isdigit()})
    else:
        features['BOS'] = True
    if i < len(sent)-1:
        word1 = str(sent[i+1])
        features.update({'+1:word.lower()': word1.lower(), '+1:word.isdigit()': word1.isdigit()})
    else:
        features['EOS'] = True
    return features

def sent2features(sent):
    return [word2features(sent, i) for i in range(len(sent))]

def process_pdf_ai(pdf_path):
    """Membaca PDF dan menebak isinya menggunakan Model AI"""
    try:
        crf = joblib.load(MODEL_PATH)
    except FileNotFoundError:
        print("ERROR: File model_ducting.pkl tidak ditemukan!")
        return []

    items_found = []
    
    with pdfplumber.open(pdf_path) as pdf:
        text_tokens = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                # Trik: Ganti enter dengan token khusus agar struktur baris terjaga
                text = text.replace('\n', ' ---BARIS_BARU--- ')
                text_tokens.extend(text.split())
        
        if not text_tokens:
            return [] # PDF Kosong/Gambar

        # PREDIKSI
        X_input = [sent2features(text_tokens)]
        y_pred = crf.predict(X_input)[0]

        # PARSING HASIL (Mengubah Label menjadi Data Terstruktur)
        temp_item, temp_dim, temp_qty = [], [], []
        
        for token, label in zip(text_tokens, y_pred):
            if token == "---BARIS_BARU---":
                # Jika ketemu baris baru, simpan item sebelumnya jika lengkap
                if temp_item:
                    # Ambil Qty (Coba konversi ke angka)
                    qty_final = 0
                    if temp_qty:
                        try: qty_final = int(temp_qty[0])
                        except: qty_final = 0
                    
                    items_found.append({
                        'nama_item': " ".join(temp_item),
                        'dimensi_raw': " ".join(temp_dim),
                        'qty': qty_final
                    })
                
                # Reset penampung sementara
                temp_item, temp_dim, temp_qty = [], [], []
            else:
                if "ITEM" in label: temp_item.append(token)
                elif "DIM" in label: temp_dim.append(token)
                elif "QTY" in label: temp_qty.append(token)

    return items_found

# --- BAGIAN 2: ROUTE WEBSITE ---
@app.route('/', methods=['GET', 'POST'])
def index():
    laporan_upload = []
    
    if request.method == 'POST':
        if 'pdf_files' not in request.files:
            return redirect(request.url)
            
        files = request.files.getlist('pdf_files')
        
        for file in files:
            if file.filename == '': continue
            
            # 1. Simpan File
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # 2. Panggil AI
            items = process_pdf_ai(file_path)
            
            # 3. Tentukan Status (Merah/Hijau)
            status = 'aman' if items else 'bahaya'
            
            # 4. Simpan hasil untuk dikirim ke HTML
            # Kita buat format tanggal cantik
            tgl = datetime.datetime.now().strftime("%d/%m/%Y")
            
            laporan_upload.append({
                'nama_file': filename,
                'file_url': url_for('static', filename='uploads/' + filename),
                'tanggal_upload': tgl,
                'items': items,
                'status': status,
                'items_count': len(items)
            })
            
        return render_template('index.html', laporan_upload=laporan_upload, mode_hasil=True)

    return render_template('index.html', mode_hasil=False)

if __name__ == '__main__':
    app.run(debug=True)