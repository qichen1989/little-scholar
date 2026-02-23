import os, json, sqlite3, functools, requests as req_lib
from flask import Flask, request, jsonify, send_from_directory, session, g, redirect, url_for
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
from pypinyin import pinyin, Style
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")

# SECRET_KEY must be a fixed string so sessions survive restarts.
# If missing, crash loudly rather than silently generating a random one.
_secret = os.environ.get("SECRET_KEY")
if not _secret:
    raise RuntimeError(
        "SECRET_KEY env var is not set. "
        "Set it to any long random string on Render so sessions survive restarts."
    )
app.secret_key = _secret

CORS(app, supports_credentials=True)

GOOGLE_VISION_KEY = os.environ["GOOGLE_VISION_API_KEY"]
DB_PATH           = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "data.db"))
ALLOWED_EMAILS    = {e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()}

# ── Google OAuth ──────────────────────────────────────────────────────────────
oauth  = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# ── DB ────────────────────────────────────────────────────────────────────────
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
        # Check if table already exists and what schema it has
        row = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='store'"
        ).fetchone()

        if row is None:
            # Fresh install — create with user column
            db.execute("""
                CREATE TABLE store (
                    user  TEXT NOT NULL,
                    key   TEXT NOT NULL,
                    value TEXT NOT NULL,
                    PRIMARY KEY (user, key)
                )
            """)
            print("DB: created new store table")

        elif "user" not in row[0]:
            # Old single-user schema — migrate to multi-user
            print("DB: migrating old schema to multi-user…")
            db.execute("ALTER TABLE store ADD COLUMN user TEXT NOT NULL DEFAULT 'main'")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_store_user_key ON store(user, key)")
            print("DB: migration complete — existing data kept under user='main'")

        else:
            print("DB: schema already up to date")

        db.commit()
    print("DB ready:", DB_PATH)

init_db()

# ── CC-CEDICT ─────────────────────────────────────────────────────────────────
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

# ── Auth ──────────────────────────────────────────────────────────────────────
def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

def current_user():
    return session.get("user", "")

# ── Pages ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("templates", "index.html")

# ── Google OAuth routes ───────────────────────────────────────────────────────
@app.route("/auth/google")
def auth_google():
    callback_url = url_for("auth_google_callback", _external=True)
    return google.authorize_redirect(callback_url)

@app.route("/auth/google/callback")
def auth_google_callback():
    token     = google.authorize_access_token()
    user_info = token.get("userinfo")
    if not user_info:
        return "Login failed: could not get user info", 400

    email = user_info.get("email", "").lower()
    name  = user_info.get("name", email)

    if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
        return f"""<html><body style="font-family:sans-serif;text-align:center;padding:60px">
          <h2>⛔ Access denied</h2>
          <p>{email} is not on the allowed list.</p>
          <a href="/">← Back</a></body></html>""", 403

    session["authenticated"] = True
    session["user"]           = email
    session["name"]           = name
    session.permanent         = True
    return redirect("/")

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/me")
def me():
    return jsonify({
        "authenticated": bool(session.get("authenticated")),
        "user":          session.get("user", ""),
        "name":          session.get("name", ""),
    })

# ── Data store ────────────────────────────────────────────────────────────────
VALID_KEYS = {"unknownChars", "masteredChars", "masteredCharData", "articleHistory", "quizProgress"}

@app.route("/api/data", methods=["GET"])
@require_auth
def get_data():
    user = current_user()
    db   = get_db()
    rows = db.execute("SELECT key, value FROM store WHERE user=?", (user,)).fetchall()
    result = {r["key"]: json.loads(r["value"]) for r in rows if r["key"] in VALID_KEYS}
    for k in VALID_KEYS:
        if k not in result:
            result[k] = [] if k == "articleHistory" else {}
    return jsonify(result)

@app.route("/api/data", methods=["POST"])
@require_auth
def save_data():
    user = current_user()
    data = request.get_json()
    db   = get_db()
    for key in VALID_KEYS:
        if key in data:
            db.execute(
                "INSERT INTO store(user,key,value) VALUES(?,?,?) "
                "ON CONFLICT(user,key) DO UPDATE SET value=excluded.value",
                (user, key, json.dumps(data[key], ensure_ascii=False))
            )
    db.commit()
    return jsonify({"ok": True})

# ── OCR ───────────────────────────────────────────────────────────────────────
@app.route("/api/ocr", methods=["POST"])
@require_auth
def ocr():
    data = request.get_json()
    b64  = data.get("image_base64")
    if not b64: return jsonify({"error": "Missing image_base64"}), 400
    url     = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_KEY}"
    payload = {"requests": [{"image": {"content": b64},
        "features": [{"type": "DOCUMENT_TEXT_DETECTION", "maxResults": 1}],
        "imageContext": {"languageHints": ["zh-Hans", "zh-Hant"]}}]}
    resp = req_lib.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if "error" in result: return jsonify({"error": result["error"]["message"]}), 500
    annotation = result["responses"][0].get("fullTextAnnotation")
    if not annotation: return jsonify({"error": "No text detected in image"}), 422
    return jsonify({"text": annotation["text"].strip()})

# ── Lookup ────────────────────────────────────────────────────────────────────
@app.route("/api/lookup", methods=["POST"])
@require_auth
def lookup():
    data       = request.get_json()
    characters = data.get("characters", [])
    result     = {}
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