import os, json, sqlite3, functools, requests
from flask import Flask, request, jsonify, send_from_directory, session, g
from flask_cors import CORS
from pypinyin import pinyin, Style
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
CORS(app, supports_credentials=True)

GOOGLE_VISION_KEY = os.environ["GOOGLE_VISION_API_KEY"]
APP_PASSWORD      = os.environ["APP_PASSWORD"]
DB_PATH           = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "data.db"))

# ── DB ──────────────────────────────────────────────────────────────────────────
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    d = os.path.dirname(DB_PATH)
    if d: os.makedirs(d, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS store (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        db.commit()
    print("DB ready:", DB_PATH)

init_db()

# ── CC-CEDICT ───────────────────────────────────────────────────────────────────
CEDICT = {}
def load_cedict():
    path = os.path.join(os.path.dirname(__file__), "cedict_ts.u8")
    if not os.path.exists(path): print("WARNING: cedict_ts.u8 not found"); return
    count = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            try:
                parts = line.split(" ", 2)
                simplified = parts[1]
                meanings = [m.strip() for m in parts[2].split("/") if m.strip() and not m.startswith("[")]
                if meanings and simplified and simplified not in CEDICT:
                    m = meanings[0]
                    CEDICT[simplified] = m[:37]+"..." if len(m)>40 else m
                    count += 1
            except: continue
    print(f"Loaded {count} CEDICT entries")
load_cedict()

# ── Auth ────────────────────────────────────────────────────────────────────────
def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    return send_from_directory("templates", "index.html")

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    if data.get("password") == APP_PASSWORD:
        session["authenticated"] = True
        session.permanent = True
        return jsonify({"ok": True})
    return jsonify({"error": "Wrong password"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/me")
def me():
    return jsonify({"authenticated": bool(session.get("authenticated"))})

# ── Key-value store ─────────────────────────────────────────────────────────────
# Stores: unknownChars, masteredChars, masteredCharData, articleHistory
VALID_KEYS = {"unknownChars", "masteredChars", "masteredCharData", "articleHistory", "quizProgress"}

@app.route("/api/data", methods=["GET"])
@require_auth
def get_data():
    db = get_db()
    rows = db.execute("SELECT key, value FROM store").fetchall()
    result = {r["key"]: json.loads(r["value"]) for r in rows if r["key"] in VALID_KEYS}
    # Fill defaults
    for k in VALID_KEYS:
        if k not in result:
            result[k] = [] if k == "articleHistory" else {}
    return jsonify(result)

@app.route("/api/data", methods=["POST"])
@require_auth
def save_data():
    data = request.get_json()
    db = get_db()
    for key in VALID_KEYS:
        if key in data:
            db.execute(
                "INSERT INTO store(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(data[key], ensure_ascii=False))
            )
    db.commit()
    return jsonify({"ok": True})

# ── OCR ─────────────────────────────────────────────────────────────────────────
@app.route("/api/ocr", methods=["POST"])
@require_auth
def ocr():
    data = request.get_json()
    b64 = data.get("image_base64")
    if not b64: return jsonify({"error": "Missing image_base64"}), 400
    url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_KEY}"
    payload = {"requests": [{"image": {"content": b64},
        "features": [{"type": "DOCUMENT_TEXT_DETECTION", "maxResults": 1}],
        "imageContext": {"languageHints": ["zh-Hans", "zh-Hant"]}}]}
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if "error" in result: return jsonify({"error": result["error"]["message"]}), 500
    annotation = result["responses"][0].get("fullTextAnnotation")
    if not annotation: return jsonify({"error": "No text detected in image"}), 422
    return jsonify({"text": annotation["text"].strip()})

# ── Lookup ──────────────────────────────────────────────────────────────────────
@app.route("/api/lookup", methods=["POST"])
@require_auth
def lookup():
    data = request.get_json()
    characters = data.get("characters", [])
    result = {}
    for char in characters:
        py = pinyin(char, style=Style.TONE)
        result[char] = {
            "pinyin":  " ".join([p[0] for p in py]) if py else "",
            "meaning": CEDICT.get(char, "")
        }
    return jsonify({"lookup": result})

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "cedict_entries": len(CEDICT)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_ENV") == "development")