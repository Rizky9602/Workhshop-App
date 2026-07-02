"""
Flask app - BPD (ducting document) digitization.
"""
import os
import re
import pickle
import datetime
import pymysql
import pdfplumber
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
MODEL_PATH = os.path.join(BASE_DIR, "models", "model_crf.pkl")
ALLOWED_EXTENSIONS = {"pdf"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB
app.secret_key = os.environ.get("SECRET_KEY", "workshop_app_secret_key_12345")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------------------------------------------------------------------
# Database configuration & initialization
# ---------------------------------------------------------------------------
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "rizky09")
DB_NAME = os.environ.get("DB_NAME", "workshop_db")

def init_db_and_schema():
    try:
        # Create database if not exists
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD
        )
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        conn.commit()
        conn.close()

        # Create tables
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bpd_documents (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    project_name VARCHAR(255),
                    bpd_no VARCHAR(100),
                    lantai VARCHAR(100),
                    unit_area VARCHAR(100),
                    upload_date VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bpd_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    document_id INT,
                    nama_ducting VARCHAR(255),
                    join_type VARCHAR(100),
                    w VARCHAR(50),
                    h VARCHAR(50),
                    l VARCHAR(50),
                    bjls VARCHAR(50),
                    qty INT,
                    FOREIGN KEY (document_id) REFERENCES bpd_documents(id) ON DELETE CASCADE
                )
            """)
            
            # Auto-migrate: check if kebutuhan_material column exists
            cursor.execute("SHOW COLUMNS FROM bpd_items LIKE 'kebutuhan_material'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE bpd_items ADD COLUMN kebutuhan_material DOUBLE DEFAULT 0")
                print("Column kebutuhan_material added to bpd_items table.")

            # Auto-migrate: check if bpd_date column exists in bpd_documents
            cursor.execute("SHOW COLUMNS FROM bpd_documents LIKE 'bpd_date'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE bpd_documents ADD COLUMN bpd_date DATE")
                print("Column bpd_date added to bpd_documents table.")

            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(100) UNIQUE,
                    password VARCHAR(255)
                )
            """)
            
            # Create material_supports table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS material_supports (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    request_no VARCHAR(100) UNIQUE,
                    project_name VARCHAR(255),
                    bpd_ids VARCHAR(255),
                    bpd_nos TEXT,
                    corner INT DEFAULT 0,
                    mur_baut INT DEFAULT 0,
                    foam_tape INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Check if admin user exists, if not insert it
            cursor.execute("SELECT * FROM users WHERE username = 'admin'")
            if not cursor.fetchone():
                cursor.execute("INSERT INTO users (username, password) VALUES ('admin', 'admin')")
                print("Default admin user created.")
        conn.commit()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")

init_db_and_schema()

def calculate_material(nama_ducting, join_type, w_str, h_str, l_str, qty):
    try:
        qty_val = int(qty) if qty else 0
        if qty_val <= 0:
            return 0.0

        # Extract W, H, L numeric values
        w_nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", w_str)]
        h_nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", h_str)]
        l_nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", l_str)]

        w_max = max(w_nums) if w_nums else 0.0
        h_max = max(h_nums) if h_nums else 0.0
        l_val = l_nums[0] if l_nums else 0.0

        name_lower = nama_ducting.lower()
        join_lower = join_type.lower()

        # Check if Kategori A: Ducting Lurus, inchian, Elbow, reduser, Dop, transisi
        is_kat_a = False
        if any(x in name_lower for x in ["lurus", "inchian", "elbow", "reducer", "reduser", "dop", "transisi"]):
            is_kat_a = True

        if is_kat_a:
            # W + H + (90 if TFD else 20)
            # Factor: if L <= 520: 1, else: 2
            # Dop & transisi: jika tidak ada tingginya langsung x 2
            adder = 90
            if "sisip" in join_lower:
                adder = 20
            
            factor = 1 if l_val <= 520 else 2
            
            if h_max == 0.0:
                requirement = (w_max + adder) * factor * qty_val * 2
            else:
                requirement = (w_max + h_max + adder) * factor * qty_val
            return float(requirement)
        else:
            # Kategori B: Cabang TY, Cabang Tee, Tee Kros, etc.
            w_second = w_nums[1] if len(w_nums) > 1 else 0.0
            
            # Determine total joints based on component type
            if "tee" in name_lower or "t-joint" in name_lower:
                total_joints = 3
            elif any(x in name_lower for x in ["dop", "cap", "end"]):
                total_joints = 1
            else:
                total_joints = 2
            
            # Parse joint counts
            num_tfd = 0
            num_sisip = 0
            if "semua" in join_lower:
                if "tfd" in join_lower:
                    num_tfd = total_joints
                elif "sisip" in join_lower:
                    num_sisip = total_joints
            elif "/" in join_lower:
                parts = join_lower.split("/")
                num_tfd = sum(1 for p in parts if "tfd" in p)
                num_sisip = sum(1 for p in parts if "sisip" in p)
            else:
                if "tfd" in join_lower:
                    num_tfd = total_joints
                elif "sisip" in join_lower:
                    num_sisip = total_joints
                else:
                    num_tfd = total_joints

            joint_factor = (num_tfd * 45) + (num_sisip * 10)
            requirement = ((w_max + h_max) + w_second + joint_factor) * 2 * qty_val
            return float(requirement)
    except Exception as e:
        print(f"Error calculating material for {nama_ducting}: {e}")
        return 0.0

def parse_indo_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip().lower()
    
    months = {
        "januari": "01", "jan": "01",
        "februari": "02", "feb": "02",
        "maret": "03", "mar": "03",
        "april": "04", "apr": "04",
        "mei": "05",
        "juni": "06", "jun": "06",
        "juli": "07", "jul": "07",
        "agustus": "08", "agu": "08", "agt": "08",
        "september": "09", "sep": "09",
        "oktober": "10", "okt": "10",
        "november": "11", "nov": "11",
        "desember": "12", "des": "12"
    }
    
    # 1. Match YYYY-MM-DD or YYYY/MM/DD
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", date_str)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        
    # 2. Match DD-MM-YYYY or DD/MM/YYYY
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})$", date_str)
    if m:
        d = m.group(1).zfill(2)
        mm = m.group(2).zfill(2)
        y = m.group(3)
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{mm}-{d}"
        
    # 3. Match DD Month YYYY or DD-Month-YYYY
    m = re.match(r"^(\d{1,2})\s*[-]?\s*([a-z]+)\s*[-]?\s*(\d{4})$", date_str)
    if m:
        d = m.group(1).zfill(2)
        month_name = m.group(2)
        y = m.group(3)
        mm = months.get(month_name, "01")
        return f"{y}-{mm}-{d}"
        
    return None

def get_roman_month(month_num):
    romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    if 1 <= month_num <= 12:
        return romans[month_num - 1]
    return "I"

def get_next_support_request_no(cursor, date_obj=None):
    import datetime
    if not date_obj:
        date_obj = datetime.date.today()
    month_num = date_obj.month
    year_num = date_obj.year
    
    roman_month = get_roman_month(month_num)
    year_2digit = str(year_num)[2:]
    
    pattern = f"%/{roman_month}/{year_2digit}"
    cursor.execute("""
        SELECT request_no FROM material_supports 
        WHERE request_no LIKE %s
    """, (pattern,))
    rows = cursor.fetchall()
    
    max_seq = 0
    for r in rows:
        req_no = r["request_no"] if isinstance(r, dict) else r[0]
        parts = req_no.split("/")
        if parts:
            try:
                seq = int(parts[0])
                if seq > max_seq:
                    max_seq = seq
            except ValueError:
                pass
                
    next_seq = max_seq + 1
    return f"{next_seq}/{roman_month}/{year_2digit}"

def calculate_material_support_for_bpds(cursor, bpd_ids):
    import math
    if not bpd_ids:
        return [], 0, 0, 0
        
    format_strings = ','.join(['%s'] * len(bpd_ids))
    query = f"""
        SELECT bi.*, bd.bpd_no, bd.project_name, bd.lantai, bd.unit_area
        FROM bpd_items bi
        JOIN bpd_documents bd ON bi.document_id = bd.id
        WHERE bi.document_id IN ({format_strings})
    """
    cursor.execute(query, tuple(bpd_ids))
    items = cursor.fetchall()
    
    calculated_items = []
    total_corner = 0
    total_murbaut = 0
    total_foam_tape_raw = 0.0
    
    for item in items:
        if not isinstance(item, dict):
            desc = cursor.description
            item = {desc[idx][0]: item[idx] for idx in range(len(desc))}
            
        nama_ducting = item.get("nama_ducting", "")
        join_type = item.get("join_type", "")
        w_str = item.get("w", "")
        h_str = item.get("h", "")
        qty = item.get("qty", 0) or 0
        
        w_parts = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", w_str)]
        h_parts = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", h_str)]
        
        name_lower = nama_ducting.lower()
        if "tee" in name_lower or "t-joint" in name_lower:
            total_joints = 3
        elif any(x in name_lower for x in ["dop", "cap", "end"]):
            total_joints = 1
        else:
            total_joints = 2
            
        join_lower = join_type.lower()
        
        size_joints = []
        if "semua" in join_lower:
            if "tfd" in join_lower:
                size_joints = ["TFD"] * total_joints
            elif "sisip" in join_lower:
                size_joints = ["SISIP"] * total_joints
            else:
                size_joints = ["TFD"] * total_joints
        elif "/" in join_lower:
            parts = [p.strip().upper() for p in join_lower.split("/") if p.strip()]
            for j in range(total_joints):
                if len(parts) > j:
                    size_joints.append(parts[j])
                else:
                    size_joints.append(parts[0] if parts else "TFD")
        else:
            if "tfd" in join_lower:
                size_joints = ["TFD"] * total_joints
            elif "sisip" in join_lower:
                size_joints = ["SISIP"] * total_joints
            else:
                size_joints = ["TFD"] * total_joints
                
        corner_item = 0
        murbaut_item = 0
        foam_tape_item_raw = 0.0
        tfd_details = []
        
        for j in range(total_joints):
            joint_t = size_joints[j]
            if "TFD" in joint_t:
                w_val = w_parts[j] if len(w_parts) > j else (w_parts[0] if w_parts else 0.0)
                h_val = h_parts[j] if len(h_parts) > j else (h_parts[0] if h_parts else 0.0)
                
                corner_j = 4 * qty
                murbaut_j = 2 * qty
                foam_tape_j_raw = (w_val + h_val) * 2 * qty / 6000.0
                
                corner_item += corner_j
                murbaut_item += murbaut_j
                foam_tape_item_raw += foam_tape_j_raw
                
                tfd_details.append(f"{w_val}x{h_val} (TFD)")
                
        if corner_item > 0:
            foam_tape_item = math.ceil(foam_tape_item_raw)
            total_corner += corner_item
            total_murbaut += murbaut_item
            total_foam_tape_raw += foam_tape_item_raw
            
            formatted_tfd_size = " / ".join(tfd_details)
            calculated_items.append({
                "nama_ducting": nama_ducting,
                "bpd_no": item.get("bpd_no", ""),
                "lantai": item.get("lantai", ""),
                "unit_area": item.get("unit_area", ""),
                "join_type": join_type,
                "w": w_str,
                "h": h_str,
                "qty": qty,
                "formatted_tfd_size": formatted_tfd_size,
                "corner": corner_item,
                "murbaut": murbaut_item,
                "foam_tape": foam_tape_item
            })
            
    total_foam_tape = math.ceil(total_foam_tape_raw) if total_foam_tape_raw > 0 else 0
    return calculated_items, total_corner, total_murbaut, total_foam_tape

def backfill_existing_data():
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor() as cursor:
            # Backfill bpd_date for existing documents
            cursor.execute("SELECT id, upload_date FROM bpd_documents WHERE bpd_date IS NULL")
            doc_rows = cursor.fetchall()
            if doc_rows:
                print(f"Found {len(doc_rows)} documents with null bpd_date. Backfilling dates...")
                for d_row in doc_rows:
                    doc_id = d_row[0]
                    up_date = d_row[1] or ""
                    parsed_date = parse_indo_date(up_date)
                    if parsed_date:
                        cursor.execute("UPDATE bpd_documents SET bpd_date = %s WHERE id = %s", (parsed_date, doc_id))
                conn.commit()
                print("Document date backfill completed.")

            # Query items that have 0 or null kebutuhan_material to calculate and update them
            cursor.execute("SELECT id, nama_ducting, join_type, w, h, l, qty FROM bpd_items WHERE kebutuhan_material = 0 OR kebutuhan_material IS NULL")
            rows = cursor.fetchall()
            if rows:
                print(f"Found {len(rows)} items with missing material requirements. Backfilling...")
                for row in rows:
                    row_id = row[0]
                    name = row[1] or ""
                    j_type = row[2] or ""
                    w_val = row[3] or ""
                    h_val = row[4] or ""
                    l_val = row[5] or ""
                    qty_val = row[6] or 0
                    
                    mat_req = calculate_material(name, j_type, w_val, h_val, l_val, qty_val)
                    cursor.execute("UPDATE bpd_items SET kebutuhan_material = %s WHERE id = %s", (mat_req, row_id))
                conn.commit()
                print("Item material backfill completed successfully.")
        conn.close()
    except Exception as e:
        print(f"Warning: Backfill failed: {e}")

backfill_existing_data()


# ---------------------------------------------------------------------------
# Load the CRF model once at startup
# ---------------------------------------------------------------------------
_crf_model = None

def get_model():
    global _crf_model
    if _crf_model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"CRF model not found at {MODEL_PATH}. "
                "Place your trained model_crf.pkl inside the models/ folder."
            )
        with open(MODEL_PATH, "rb") as f:
            _crf_model = pickle.load(f)
    return _crf_model

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------------------------------------------------------------------
# 1. PDF -> tokens (pdfplumber)
# ---------------------------------------------------------------------------
def tokenize_pdf(filepath):
    sentences = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue
                tokens = line.split()
                if tokens:
                    sentences.append(tokens)
    return sentences

# ---------------------------------------------------------------------------
# 2. Token -> CRF features
# ---------------------------------------------------------------------------
def word2features(sent, i):
    word = str(sent[i])

    features = {
        'bias': 1.0,
        'word.lower()': word.lower(),
        'word.isupper()': word.isupper(),
        'word.istitle()': word.istitle(),
        'word.isdigit()': word.isdigit(),
        'has_x': 'x' in word.lower(),
        'has_slash': '/' in word,
        'has_equal': '=' in word,
        'has_Hyphen' : '-' in word,
        'is_p_or_s': word.lower() in ['p', 's'],
    }

    if i > 0:
        word1 = str(sent[i-1])
        features.update({
            '-1:word.lower()': word1.lower(),
            '-1:word.isdigit()': word1.isdigit(),
            '-1:word.isupper()': word1.isupper(),
        })
    else:
        features['BOS'] = True

    if i < len(sent)-1:
        word1 = str(sent[i+1])
        features.update({
            '+1:word.lower()': word1.lower(),
            '+1:word.isdigit()': word1.isdigit(),
            '+1:word.isupper()': word1.isupper(),
        })
    else:
        features['EOS'] = True

    return features

def sent2features(sent):
    return [word2features(sent, i) for i in range(len(sent))]

# ---------------------------------------------------------------------------
# 3. Run CRF + group BIO tags into entities
# ---------------------------------------------------------------------------
def predict_tags(sentences):
    model = get_model()
    X = [sent2features(s) for s in sentences]
    y_pred = model.predict(X)
    return y_pred

def group_entities(sentences, tag_sequences):
    entities = []
    for tokens, tags in zip(sentences, tag_sequences):
        current_label = None
        current_tokens = []

        def flush():
            if current_label and current_tokens:
                entities.append({
                    "label": current_label,
                    "text": " ".join(current_tokens),
                })

        for tok, tag in zip(tokens, tags):
            if tag == "O":
                flush()
                current_label, current_tokens = None, []
                continue

            prefix, _, label = tag.partition("-")
            if prefix == "B":
                flush()
                current_label = label
                current_tokens = [tok]
            elif prefix == "I" and label == current_label:
                current_tokens.append(tok)
            else:
                flush()
                current_label = label
                current_tokens = [tok]
        flush()
    return entities

# ---------------------------------------------------------------------------
# 4. Reshape entities into the table/header structure
# ---------------------------------------------------------------------------
def split_dimension(dim_text):
    # Find all occurrences of W x H (e.g. 500x300, 400x300, etc.)
    matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*[xX]\s*(\d+(?:[.,]\d+)?)", dim_text)
    
    if not matches:
        return "", "", dim_text
    
    # Extract and combine widths and heights with '/'
    widths = [m[0] for m in matches]
    heights = [m[1] for m in matches]
    w = "/".join(widths)
    h = "/".join(heights)
    
    # Get the remaining text after removing all W x H matches
    remaining = dim_text
    for match_item in re.finditer(r"(\d+(?:[.,]\d+)?)\s*[xX]\s*(\d+(?:[.,]\d+)?)", dim_text):
        remaining = remaining.replace(match_item.group(0), "", 1)
    remaining = remaining.strip()
    
    l_val = ""
    # Check if there is a slash '/' in the text and parse the length part
    if "/" in dim_text:
        parts = dim_text.split("/")
        last_part = parts[-1].strip()
        clean_last = re.sub(r"^[lLpP]\s*=\s*", "", last_part).strip()
        # If the last part is not a dimension match itself, it's our length
        if not re.search(r"\d+\s*[xX]\s*\d+", last_part):
            l_val = clean_last
        else:
            l_val = remaining
    else:
        l_val = remaining

    # Clean up leading 'x', 'X', '-', '/', or spaces
    l_val = re.sub(r"^[xX\-/]\s*", "", l_val).strip()
    # Clean up leading 'L=' or 'L =', or 'P=' or 'P =' (case-insensitive)
    l_val = re.sub(r"^[lLpP]\s*=\s*", "", l_val).strip()
    
    # If length contains only slashes, question marks, spaces, or is empty, default to "0"
    l_val = l_val.strip()
    if not l_val or all(c in "/? " for c in l_val):
        l_val = "0"
    
    return w, h, l_val

def build_result(entities):
    months_id = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    today = datetime.date.today()
    indo_date = f"{today.day} {months_id[today.month]} {today.year}"

    header = {
        "project_name": "",
        "bpd_no": "",
        "date": indo_date,
        "unit_area": "",
        "lantai": ""
    }
    rows = []
    current_row = {}

    def flush_row():
        if current_row:
            rows.append({
                "nama_ducting": current_row.get("ITEM", ""),
                "join_type": current_row.get("JOIN", ""),
                "w": current_row.get("W", ""),
                "h": current_row.get("H", ""),
                "l": current_row.get("L", ""),
                "bjls": current_row.get("THICK", ""),
                "qty": current_row.get("QTY", ""),
            })

    for ent in entities:
        label, text = ent["label"], ent["text"]

        if label == "PROYEK":
            header["project_name"] = (header["project_name"] + " " + text).strip()
        elif label == "UNIT":
            header["unit_area"] = (header["unit_area"] + " " + text).strip()
        elif label == "LANTAI":
            header["lantai"] = (header["lantai"] + " " + text).strip()
        elif label == "BPD":
            header["bpd_no"] = (header["bpd_no"] + " " + text).strip()
        elif label == "ITEM":
            if "ITEM" in current_row:
                flush_row()
                current_row = {}
            current_row["ITEM"] = text
        elif label == "JOIN":
            current_row["JOIN"] = text
        elif label == "DIM":
            w, h, l = split_dimension(text)
            
            def append_val(key, val):
                if not val:
                    return
                if key in current_row and current_row[key]:
                    current_row[key] = f"{current_row[key]}/{val}"
                else:
                    current_row[key] = val
                    
            append_val("W", w)
            append_val("H", h)
            append_val("L", l)
        elif label == "THICK":
            current_row["THICK"] = text
        elif label == "QTY":
            current_row["QTY"] = text

    flush_row()
    return {"header": header, "rows": rows}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.before_request
def check_login():
    public_endpoints = ["login", "static", "serve_uploaded_file"]
    endpoint = request.endpoint
    if endpoint in public_endpoints or not endpoint:
        return
        
    if not session.get("logged_in"):
        return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        try:
            conn = pymysql.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Parameterized query to prevent SQL injection
                cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
                user = cursor.fetchone()
            conn.close()
            
            if user:
                session["logged_in"] = True
                return redirect(url_for("index"))
            else:
                error = "Username atau password salah!"
        except Exception as e:
            error = f"Database error: {e}"
            
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

# Route untuk halaman utama / dashboard (merujuk ke index.html)
@app.route("/")
def index():
    return render_template("index.html")

# Route untuk halaman upload (merujuk ke Upload.html)
@app.route("/upload")
def upload_page():
    # Huruf 'U' besar di sini harus sama persis dengan nama file di folder templates
    return render_template("Upload.html")

# Route untuk halaman BPD management dengan filter pencarian
@app.route("/bpd-management")
def bpd_management():
    project_filter = request.args.get("project", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    
    query = "SELECT * FROM bpd_documents WHERE 1=1"
    params = []
    
    if project_filter:
        query += " AND project_name = %s"
        params.append(project_filter)
        
    if start_date:
        query += " AND DATE(created_at) >= %s"
        params.append(start_date)
        
    if end_date:
        query += " AND DATE(created_at) <= %s"
        params.append(end_date)
        
    query += " ORDER BY bpd_date DESC, bpd_no DESC"
    
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Query distinct projects for dropdown
            cursor.execute("SELECT DISTINCT project_name FROM bpd_documents WHERE project_name IS NOT NULL AND project_name != '' ORDER BY project_name")
            projects = [r["project_name"] for r in cursor.fetchall()]
            
            # Query filtered BPD documents
            cursor.execute(query, params)
            documents = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"Warning: Gagal memuat data BPD management: {e}")
        projects = []
        documents = []
        
    return render_template(
        "bpd_management.html", 
        documents=documents, 
        projects=projects,
        selected_project=project_filter,
        start_date=start_date,
        end_date=end_date
    )

# Route untuk halaman detail BPD
@app.route("/bpd-detail/<int:doc_id>")
def bpd_detail(doc_id):
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM bpd_documents WHERE id = %s", (doc_id,))
            document = cursor.fetchone()
            if not document:
                return "Dokumen BPD tidak ditemukan", 404
            
            cursor.execute("SELECT * FROM bpd_items WHERE document_id = %s", (doc_id,))
            items = cursor.fetchall()
            
            for item in items:
                w_val = item.get("w", "")
                h_val = item.get("h", "")
                l_val = item.get("l", "")
                
                w_parts = [p.strip() for p in w_val.split("/") if p.strip()]
                h_parts = [p.strip() for p in h_val.split("/") if p.strip()]
                
                pairs = []
                max_len = max(len(w_parts), len(h_parts))
                for i in range(max_len):
                    w_part = w_parts[i] if i < len(w_parts) else "0"
                    h_part = h_parts[i] if i < len(h_parts) else "0"
                    pairs.append(f"{w_part} x {h_part}")
                
                size_str = " / ".join(pairs)
                if l_val and l_val.strip() != "0":
                    size_str = f"{size_str} / {l_val}"
                
                item["formatted_size"] = size_str
            
            # Aggregate material usage by BJLS thickness
            bjls_summary = {}
            for item in items:
                bjls_val = item.get("bjls", "").strip()
                if not bjls_val:
                    bjls_val = "Tanpa BJLS"
                
                mat_req = item.get("kebutuhan_material", 0.0) or 0.0
                bjls_summary[bjls_val] = bjls_summary.get(bjls_val, 0.0) + mat_req
                
            # Sort BJLS dynamically (numeric thickness first)
            def bjls_sort_key(k):
                try:
                    return float(re.findall(r"\d+(?:\.\d+)?", k)[0])
                except:
                    return 999.0
            
            sorted_bjls = []
            for k in sorted(bjls_summary.keys(), key=bjls_sort_key):
                sorted_bjls.append({
                    "bjls": k,
                    "total_material": bjls_summary[k]
                })
        conn.close()
    except Exception as e:
        return f"Terjadi kesalahan saat memuat data: {e}", 500
    
    return render_template("bpd_detail.html", document=document, items=items, bjls_summary=sorted_bjls)

# Route untuk cetak laporan bulanan (per proyek atau semua proyek)
@app.route("/bpd-report")
def bpd_report():
    project_filter = request.args.get("project", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    doc_query = "SELECT id, project_name FROM bpd_documents WHERE 1=1"
    doc_params = []
    if project_filter:
        doc_query += " AND project_name = %s"
        doc_params.append(project_filter)
    if start_date:
        doc_query += " AND DATE(created_at) >= %s"
        doc_params.append(start_date)
    if end_date:
        doc_query += " AND DATE(created_at) <= %s"
        doc_params.append(end_date)

    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(doc_query, doc_params)
            documents = cursor.fetchall()
            
            if not documents:
                conn.close()
                return render_template(
                    "bpd_report.html",
                    project_filter=project_filter,
                    start_date=start_date,
                    end_date=end_date,
                    report_by_project={},
                    single_project=None
                )
                
            doc_ids = [d["id"] for d in documents]
            format_strings = ','.join(['%s'] * len(doc_ids))
            cursor.execute(f"""
                SELECT bi.*, bd.project_name 
                FROM bpd_items bi 
                JOIN bpd_documents bd ON bi.document_id = bd.id 
                WHERE bi.document_id IN ({format_strings})
            """, tuple(doc_ids))
            items = cursor.fetchall()
        conn.close()
    except Exception as e:
        return f"Terjadi kesalahan saat membuat laporan: {e}", 500

    # Group items by project, then by BJLS
    report_by_project = {}
    for item in items:
        p_name = item["project_name"]
        bjls_val = item.get("bjls", "").strip()
        if not bjls_val:
            bjls_val = "Tanpa BJLS"
        mat_req = item.get("kebutuhan_material", 0.0) or 0.0
        
        if p_name not in report_by_project:
            report_by_project[p_name] = {}
        report_by_project[p_name][bjls_val] = report_by_project[p_name].get(bjls_val, 0.0) + mat_req

    def bjls_sort_key(k):
        try:
            return float(re.findall(r"\d+(?:\.\d+)?", k)[0])
        except:
            return 999.0

    formatted_report = {}
    for proj, bjls_dict in report_by_project.items():
        sorted_items = []
        for k in sorted(bjls_dict.keys(), key=bjls_sort_key):
            sorted_items.append({
                "bjls": k,
                "total_material": bjls_dict[k]
            })
        formatted_report[proj] = sorted_items

    single_project = project_filter if project_filter else None

    return render_template(
        "bpd_report.html",
        project_filter=project_filter,
        start_date=start_date,
        end_date=end_date,
        report_by_project=formatted_report,
        single_project=single_project
    )

# Route untuk menghapus dokumen BPD beserta itemnya
@app.route("/api/delete-bpd/<int:doc_id>", methods=["POST"])
def delete_bpd(doc_id):
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor() as cursor:
            # Delete the document (ON DELETE CASCADE handles bpd_items automatically)
            cursor.execute("DELETE FROM bpd_documents WHERE id = %s", (doc_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "BPD berhasil dihapus."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Route untuk halaman Material Support
@app.route("/material-support")
def material_support():
    project_filter = request.args.get("project", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    
    query = "SELECT * FROM material_supports WHERE 1=1"
    params = []
    
    if project_filter:
        query += " AND project_name = %s"
        params.append(project_filter)
        
    if start_date:
        query += " AND DATE(created_at) >= %s"
        params.append(start_date)
        
    if end_date:
        query += " AND DATE(created_at) <= %s"
        params.append(end_date)
        
    query += " ORDER BY created_at DESC"
    
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Distinct projects from material_supports
            cursor.execute("SELECT DISTINCT project_name FROM material_supports WHERE project_name IS NOT NULL AND project_name != '' ORDER BY project_name")
            projects = [r["project_name"] for r in cursor.fetchall()]
            
            # If empty, fallback to bpd_documents
            if not projects:
                cursor.execute("SELECT DISTINCT project_name FROM bpd_documents WHERE project_name IS NOT NULL AND project_name != '' ORDER BY project_name")
                projects = [r["project_name"] for r in cursor.fetchall()]
                
            cursor.execute(query, params)
            requests_list = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"Warning: Gagal memuat data Material Support: {e}")
        projects = []
        requests_list = []
        
    return render_template(
        "material_support.html",
        requests=requests_list,
        projects=projects,
        selected_project=project_filter,
        start_date=start_date,
        end_date=end_date
    )

# Route untuk halaman tambah Material Support
@app.route("/material-support/create")
def material_support_create():
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT DISTINCT project_name FROM bpd_documents WHERE project_name IS NOT NULL AND project_name != '' ORDER BY project_name")
            projects = [r["project_name"] for r in cursor.fetchall()]
        conn.close()
    except Exception as e:
        print(f"Error fetching projects: {e}")
        projects = []
        
    return render_template("material_support_create.html", projects=projects)

# API untuk mendapatkan BPD berdasarkan proyek
@app.route("/api/project-bpds/<path:project_name>")
def api_project_bpds(project_name):
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT id, bpd_no, lantai, unit_area, upload_date, created_at 
                FROM bpd_documents 
                WHERE project_name = %s 
                ORDER BY bpd_date DESC, bpd_no DESC
            """, (project_name,))
            bpds = cursor.fetchall()
        conn.close()
        
        for b in bpds:
            if b.get("created_at"):
                b["created_at"] = b["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                
        return jsonify({"success": True, "bpds": bpds})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# API untuk kalkulasi pratinjau material support
@app.route("/api/calculate-support", methods=["POST"])
def api_calculate_support():
    try:
        data = request.json or {}
        bpd_ids = data.get("bpd_ids", [])
        if not bpd_ids:
            return jsonify({"success": False, "error": "Tidak ada BPD yang dipilih."}), 400
            
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            calculated_items, total_corner, total_murbaut, total_foam_tape = calculate_material_support_for_bpds(cursor, bpd_ids)
        conn.close()
        
        return jsonify({
            "success": True,
            "items": calculated_items,
            "total_corner": total_corner,
            "total_murbaut": total_murbaut,
            "total_foam_tape": total_foam_tape
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# API untuk menyimpan data Material Support
@app.route("/api/save-support", methods=["POST"])
def api_save_support():
    try:
        data = request.json or {}
        project_name = data.get("project_name", "").strip()
        bpd_ids = data.get("bpd_ids", [])
        
        if not project_name:
            return jsonify({"success": False, "error": "Nama proyek kosong."}), 400
        if not bpd_ids:
            return jsonify({"success": False, "error": "Tidak ada BPD yang dipilih."}), 400
            
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Get BPD numbers
            format_strings = ','.join(['%s'] * len(bpd_ids))
            cursor.execute(f"SELECT bpd_no FROM bpd_documents WHERE id IN ({format_strings}) ORDER BY bpd_no", tuple(bpd_ids))
            bpd_nos_list = [r["bpd_no"] for r in cursor.fetchall()]
            bpd_nos_str = ", ".join(bpd_nos_list)
            bpd_ids_str = ",".join(str(x) for x in bpd_ids)
            
            # Calculate support totals
            _, total_corner, total_murbaut, total_foam_tape = calculate_material_support_for_bpds(cursor, bpd_ids)
            
            # Generate sequential request number
            import datetime
            today = datetime.date.today()
            request_no = get_next_support_request_no(cursor, today)
            
            cursor.execute("""
                INSERT INTO material_supports (request_no, project_name, bpd_ids, bpd_nos, corner, mur_baut, foam_tape)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (request_no, project_name, bpd_ids_str, bpd_nos_str, total_corner, total_murbaut, total_foam_tape))
            
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Material support berhasil disimpan!", "request_no": request_no})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Route untuk halaman detail/cetak Material Support
@app.route("/material-support/detail/<int:req_id>")
def material_support_detail(req_id):
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM material_supports WHERE id = %s", (req_id,))
            request_data = cursor.fetchone()
            if not request_data:
                conn.close()
                return "Permintaan Material Support tidak ditemukan", 404
                
            bpd_ids_str = request_data.get("bpd_ids", "")
            if bpd_ids_str:
                bpd_ids = [int(x) for x in bpd_ids_str.split(",") if x.strip()]
            else:
                bpd_ids = []
                
            calculated_items, _, _, _ = calculate_material_support_for_bpds(cursor, bpd_ids)
        conn.close()
        
        return render_template(
            "material_support_detail.html",
            request_data=request_data,
            items=calculated_items
        )
    except Exception as e:
        return f"Terjadi kesalahan saat memuat detail: {e}", 500

# API untuk menghapus Material Support
@app.route("/api/delete-support/<int:req_id>", methods=["POST"])
def api_delete_support(req_id):
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM material_supports WHERE id = %s", (req_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Permintaan Material Support berhasil dihapus."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Route untuk API dashboard stats
@app.route("/api/dashboard-stats")
def dashboard_stats():
    try:
        import datetime
        now = datetime.datetime.now()
        current_year = now.year
        current_month = now.month

        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Get total documents uploaded this month
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM bpd_documents 
                WHERE MONTH(bpd_date) = %s AND YEAR(bpd_date) = %s
            """, (current_month, current_year))
            total_bpd_this_month = cursor.fetchone()["count"]
            
            # Get active projects count overall
            cursor.execute("SELECT COUNT(DISTINCT project_name) as count FROM bpd_documents")
            active_projects = cursor.fetchone()["count"]
            
            # Generate trend data for the last 6 months dynamically
            month_names = {
                1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
                7: "Jul", 8: "Agt", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"
            }
            
            trend_labels = []
            trend_data = []
            
            # Calculate months list
            months_to_query = []
            for i in range(5, -1, -1):
                m = current_month - i
                y = current_year
                if m <= 0:
                    m += 12
                    y -= 1
                months_to_query.append((y, m))
                
            for y, m in months_to_query:
                trend_labels.append(month_names[m])
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM bpd_documents 
                    WHERE MONTH(bpd_date) = %s AND YEAR(bpd_date) = %s
                """, (m, y))
                cnt = cursor.fetchone()["count"]
                trend_data.append(cnt)
                
            # Get BJLS usage this month
            cursor.execute("""
                SELECT bi.bjls, SUM(bi.kebutuhan_material) as total 
                FROM bpd_items bi 
                JOIN bpd_documents bd ON bi.document_id = bd.id 
                WHERE MONTH(bd.bpd_date) = %s AND YEAR(bd.bpd_date) = %s
                GROUP BY bi.bjls
            """, (current_month, current_year))
            bjls_rows = cursor.fetchall()
            
            bjls_labels = []
            bjls_data = []
            for row in bjls_rows:
                bjls_val = row["bjls"].strip() if row["bjls"] else "Tanpa BJLS"
                total_val = float(row["total"] or 0.0)
                bjls_labels.append(f"BJLS {bjls_val}")
                bjls_data.append(total_val)
                
        conn.close()
        return jsonify({
            "success": True,
            "total_bpd_this_month": total_bpd_this_month,
            "active_projects": active_projects,
            "trend_labels": trend_labels,
            "trend_data": trend_data,
            "bjls_labels": bjls_labels,
            "bjls_data": bjls_data
        })
    except Exception as e:
        print(f"Error in dashboard stats: {e}")
        return jsonify({
            "success": False,
            "total_bpd_this_month": 0,
            "active_projects": 0,
            "trend_labels": ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun"],
            "trend_data": [0, 0, 0, 0, 0, 0],
            "bjls_labels": [],
            "bjls_data": []
        })

# Route untuk menyajikan file PDF yang diupload
@app.route("/uploads/<filename>")
def serve_uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# Route untuk menyimpan data BPD ke database MySQL
@app.route("/api/save-bpd", methods=["POST"])
def save_bpd():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "Data kosong."}), 400

        project_name = data.get("project_name", "")
        bpd_no = data.get("bpd_no", "")
        lantai = data.get("lantai", "")
        unit_area = data.get("unit_area", "")
        upload_date = data.get("date", "")
        rows = data.get("rows", [])

        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        with conn.cursor() as cursor:
            # Parse Indonesian date to sortable date format (YYYY-MM-DD)
            parsed_bpd_date = parse_indo_date(upload_date)

            # Insert into bpd_documents
            cursor.execute("""
                INSERT INTO bpd_documents (project_name, bpd_no, lantai, unit_area, upload_date, bpd_date)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (project_name, bpd_no, lantai, unit_area, upload_date, parsed_bpd_date))

            # Get the inserted document ID
            document_id = conn.insert_id()

            # Insert all rows into bpd_items
            for row in rows:
                qty_val = 0
                try:
                    qty_val = int(row.get("qty", 0)) if row.get("qty") else 0
                except ValueError:
                    pass

                l_val = row.get("l", "").strip()
                if l_val == "?" or l_val == "":
                    l_val = "0"

                mat_req = calculate_material(
                    row.get("nama_ducting", ""),
                    row.get("join_type", ""),
                    row.get("w", ""),
                    row.get("h", ""),
                    l_val,
                    qty_val
                )

                cursor.execute("""
                    INSERT INTO bpd_items (document_id, nama_ducting, join_type, w, h, l, bjls, qty, kebutuhan_material)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    document_id,
                    row.get("nama_ducting", ""),
                    row.get("join_type", ""),
                    row.get("w", ""),
                    row.get("h", ""),
                    l_val,
                    row.get("bjls", ""),
                    qty_val,
                    mat_req
                ))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Data BPD berhasil disimpan ke database MySQL!"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Gagal menyimpan ke database: {e}"}), 500

@app.route("/api/upload-bpd", methods=["POST"])
def upload_bpd():
    if "pdf_files" not in request.files:
        return jsonify({"success": False, "error": "Tidak ada file yang diupload."}), 400

    file = request.files["pdf_files"]

    if file.filename == "":
        return jsonify({"success": False, "error": "Nama file kosong."}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": "File harus berformat PDF."}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    try:
        sentences = tokenize_pdf(filepath)
        full_text = " ".join(tok for sent in sentences for tok in sent).upper()

        if "BPD" not in full_text:
            return jsonify({
                "success": False,
                "error": "File yang diupload bukan merupakan dokumen BPD."
            }), 422

        if not sentences:
            return jsonify({
                "success": False,
                "error": "Tidak ada teks yang dapat dibaca dari PDF (kemungkinan hasil scan gambar)."
            }), 422

        tag_sequences = predict_tags(sentences)
        entities = group_entities(sentences, tag_sequences)
        result = build_result(entities)

        return jsonify({
            "success": True,
            "filename": filename,
            "data": result,
        })

    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        return jsonify({"success": False, "error": f"Gagal memproses file: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True)