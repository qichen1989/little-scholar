# 🏮 Little Scholar (小学者)

A Chinese reading app for kids — photograph any Chinese article, get instant pinyin and meanings for every character, build a personal study list, and practice with quizzes.

Built with Flask + React (via CDN). No Anthropic/Claude API required.

![Python](https://img.shields.io/badge/python-3.10+-blue) ![Flask](https://img.shields.io/badge/flask-3.0-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## ✨ Features

- **📸 OCR** — photograph any Chinese text, Google Vision extracts it instantly
- **🔤 Pinyin** — tone-marked pinyin above every character, generated locally with pypinyin
- **📖 Meanings** — English definitions from CC-CEDICT (120k+ entries, runs offline)
- **🔊 Read aloud** — Web Speech API reads the article sentence by sentence with a seek bar
- **📌 Study list** — tap any character to save it; tap again to remove
- **⭐ Master list** — mark characters as mastered; they reappear occasionally in quizzes for review
- **🏆 Auto-promote** — pass a character in all 3 quiz types and it automatically moves to mastered
- **🎮 3 quiz modes** — Pinyin (multiple choice), Flashcards, Writing (draw on canvas)
- **🕐 Article history** — last 10 articles saved with thumbnails for quick re-opening
- **👤 Google login** — Sign in with Google; each user's data is completely separate
- **💾 Persistent storage** — SQLite on a Render disk, survives restarts and redeployments

---

## 🏗 How It Works

```
Photo upload
    ↓
Browser preprocesses image (resize + contrast)
    ↓
POST /api/ocr → Google Cloud Vision API → raw Chinese text
    ↓
POST /api/lookup → pypinyin (pinyin) + CC-CEDICT (meanings) — no API calls
    ↓
React renders article with pinyin, character tap, TTS bar
    ↓
Study list / quiz progress auto-saved to SQLite via POST /api/data
```

---

## 📁 Project Structure

```
little-scholar/
├── app.py                  # Flask backend — OAuth, OCR, lookup, data store
├── templates/
│   └── index.html          # Entire frontend (React via Babel CDN, ~900 lines)
├── cedict_ts.u8            # CC-CEDICT dictionary — download separately (see below)
├── requirements.txt
├── Procfile                # gunicorn start command for Render
├── .env.example            # Copy to .env for local dev
└── .env                    # Your secrets — never commit this
```

---

## 🚀 Running Locally

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/little-scholar.git
cd little-scholar
```

### 2. Download CC-CEDICT (one-time, ~10 MB)

```bash
# Mac / Linux
curl -L "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz" | gunzip > cedict_ts.u8

# Windows (PowerShell)
Invoke-WebRequest "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz" -OutFile cedict.gz
# Then extract cedict.gz and rename the result to cedict_ts.u8
```

### 3. Create a virtual environment

```bash
python -m venv venv

# Mac / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
GOOGLE_VISION_API_KEY=AIzaSy-your-key-here
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
SECRET_KEY=any-long-random-string-keep-it-secret
ALLOWED_EMAILS=you@gmail.com,daughter@gmail.com
FLASK_ENV=development
```

### 6. Run

```bash
python app.py
```

Open **http://localhost:5000** 🎉

> For local Google OAuth, add `http://localhost:5000/auth/google/callback` as an authorised redirect URI in your Google Cloud Console.

---

## ☁️ Deploying to Render

The app is designed for Render with a persistent disk for SQLite storage.

### Step 1 — Commit cedict_ts.u8

The dictionary is ~10 MB — fine to commit directly:

```bash
git add cedict_ts.u8
git commit -m "Add CC-CEDICT dictionary"
git push
```

### Step 2 — Create a Web Service on Render

1. Go to [render.com](https://render.com/) → **New → Web Service**
2. Connect your GitHub repo
3. Set these build settings:

| Field             | Value                                                             |
| ----------------- | ----------------------------------------------------------------- |
| **Runtime**       | Python 3                                                          |
| **Build Command** | `pip install -r requirements.txt`                                 |
| **Start Command** | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120` |
| **Instance Type** | **Starter**($7/mo) — required for persistent disk                 |

### Step 3 — Add a Persistent Disk

1. In your service → **Disks** tab → **Add Disk**
2. Set **Mount Path** to `/var/data` and **Size** to `1 GB`

### Step 4 — Set Environment Variables

Go to **Environment** tab and add:

| Key                     | Value                                                                 |
| ----------------------- | --------------------------------------------------------------------- |
| `GOOGLE_VISION_API_KEY` | Your Vision API key (`AIzaSy…`)                                       |
| `GOOGLE_CLIENT_ID`      | From Google Cloud Console                                             |
| `GOOGLE_CLIENT_SECRET`  | From Google Cloud Console                                             |
| `SECRET_KEY`            | Any long random string —**must be fixed**so sessions survive restarts |
| `ALLOWED_EMAILS`        | Comma-separated Gmail addresses, e.g.`alice@gmail.com,bob@gmail.com`  |
| `DB_PATH`               | `/var/data/data.db`                                                   |

### Step 5 — Set up Google OAuth

1. Go to [console.cloud.google.com](https://console.cloud.google.com/) → your project
2. **APIs & Services → Credentials → + Create Credentials → OAuth 2.0 Client ID**
3. Application type: **Web application**
4. Add authorised redirect URI: `https://your-app.onrender.com/auth/google/callback`
5. Copy the **Client ID** and **Client Secret** → paste into Render env vars above

### Step 6 — Deploy

Push to GitHub — Render redeploys automatically. Visit `/api/health` to confirm:

```json
{
  "status": "ok",
  "cedict_entries": 120517,
  "db": {
    "alice@gmail.com": {
      "unknownChars": "401 bytes",
      "masteredChars": "11 bytes"
    }
  }
}
```

---

## 🔑 Getting a Google Cloud Vision API Key

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Create a new project (or select your existing one)
3. Search for **Cloud Vision API** → **Enable**
4. **APIs & Services → Credentials → + Create Credentials → API Key**
5. Copy the key (starts with `AIzaSy`)

> Google gives **1,000 free Vision API requests/month** . After that it's ~$1.50 per 1,000 images.

---

## 👥 Adding Users

Add any Gmail address to the `ALLOWED_EMAILS` env var on Render (comma-separated). Each user gets their own completely isolated study list, mastered chars, and article history.

```
ALLOWED_EMAILS=daughter@gmail.com,you@gmail.com,friend@gmail.com
```

---

## 🗃 Database

Data is stored in a single SQLite file at `DB_PATH`. The schema is a simple key-value store namespaced by user email:

```sql
CREATE TABLE store (
    user  TEXT NOT NULL,
    key   TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (user, key)
);
```

Keys stored per user: `unknownChars`, `masteredChars`, `masteredCharData`, `articleHistory`, `quizProgress`.

**Schema migration** is handled automatically on startup — if an older single-user database is detected, it is migrated to the multi-user format transparently. Existing data stored under `'main'` is automatically reassigned to the first Google account that logs in.

---

## 🎮 Quiz System

Characters start in the **Study List** . Once you pass a character correctly in all three quiz types, it auto-promotes to the **Master List** with a 🏆 toast.

| Quiz         | Type            | Pass condition                |
| ------------ | --------------- | ----------------------------- |
| 🔤 Pinyin    | Multiple choice | Select correct pinyin         |
| 🃏 Flashcard | Self-graded     | Tap "Got it!"                 |
| ✍️ Writing   | Self-graded     | Draw character, tap "Got it!" |

Mastered characters reappear in future quizzes at a 25% rate (marked ⭐ REVIEW) to keep them fresh.

Progress badges (`P` `F` `W`) on each study list card show which quiz types have been passed.

---

## 🛠 Tech Stack

| Layer      | Technology                           |
| ---------- | ------------------------------------ |
| Backend    | Python / Flask                       |
| Frontend   | React 18 (via CDN), Babel standalone |
| OCR        | Google Cloud Vision API              |
| Pinyin     | pypinyin (runs locally)              |
| Dictionary | CC-CEDICT (runs locally)             |
| TTS        | Web Speech API (browser built-in)    |
| Auth       | Google OAuth 2.0 via Authlib         |
| Database   | SQLite                               |
| Hosting    | Render (Starter plan)                |

---

## 📄 License

MIT
