import os
import functools
import requests
from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from pypinyin import pinyin, Style
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
CORS(app, supports_credentials=True)

GOOGLE_VISION_KEY = os.environ["GOOGLE_VISION_API_KEY"]
APP_PASSWORD = os.environ["APP_PASSWORD"]  # set this in .env

# ── Load CC-CEDICT dictionary ──────────────────────────────────────────────────
CEDICT = {}

def load_cedict():
    dict_path = os.path.join(os.path.dirname(__file__), "cedict_ts.u8")
    if not os.path.exists(dict_path):
        print("WARNING: cedict_ts.u8 not found — meanings will be empty. See README.")
        return
    count = 0
    with open(dict_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                parts = line.split(" ", 2)
                simplified = parts[1]
                rest = parts[2]
                meanings = [m.strip() for m in rest.split("/") if m.strip() and not m.startswith("[")]
                if meanings and simplified and simplified not in CEDICT:
                    meaning = meanings[0]
                    if len(meaning) > 40:
                        meaning = meaning[:37] + "..."
                    CEDICT[simplified] = meaning
                    count += 1
            except Exception:
                continue
    print(f"Loaded {count} CEDICT entries")

load_cedict()


# ── Auth helper ────────────────────────────────────────────────────────────────
def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Serve frontend ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("templates", "index.html")


# ── Auth endpoints ─────────────────────────────────────────────────────────────
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


# ── OCR endpoint ───────────────────────────────────────────────────────────────
@app.route("/api/ocr", methods=["POST"])
@require_auth
def ocr():
    data = request.get_json()
    image_base64 = data.get("image_base64")
    if not image_base64:
        return jsonify({"error": "Missing image_base64"}), 400

    url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_KEY}"
    payload = {
        "requests": [{
            "image": {"content": image_base64},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION", "maxResults": 1}],
            "imageContext": {"languageHints": ["zh-Hans", "zh-Hant"]}
        }]
    }

    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    if "error" in result:
        return jsonify({"error": result["error"]["message"]}), 500

    annotation = result["responses"][0].get("fullTextAnnotation")
    if not annotation:
        return jsonify({"error": "No text detected in image"}), 422

    return jsonify({"text": annotation["text"].strip()})


# ── Pinyin lookup endpoint ─────────────────────────────────────────────────────
@app.route("/api/lookup", methods=["POST"])
@require_auth
def lookup():
    data = request.get_json()
    characters = data.get("characters", [])
    if not characters:
        return jsonify({"lookup": {}}), 200

    result = {}
    for char in characters:
        py = pinyin(char, style=Style.TONE)
        pinyin_str = " ".join([p[0] for p in py]) if py else ""
        meaning = CEDICT.get(char, "")
        if not meaning and len(char) > 1:
            meaning = CEDICT.get(char[0], "")
        result[char] = {"pinyin": pinyin_str, "meaning": meaning}

    return jsonify({"lookup": result})


# ── Health check ───────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "cedict_entries": len(CEDICT)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_ENV") == "development")