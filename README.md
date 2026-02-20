# 🏮 Little Scholar (小学者)

A Chinese reading app for kids — uses **Google Cloud Vision** for OCR, **pypinyin** for tone-marked pinyin, and **CC-CEDICT** for English meanings. **No Anthropic/Claude API needed.**

---

## Prerequisites

- Python 3.10+
- A **Google Cloud Vision API key** (see below)

---

## Getting Your Google Cloud Vision API Key

1. Go to https://console.cloud.google.com
2. Create a new project (or select an existing one)
3. Search for **"Cloud Vision API"** → click **Enable**
4. Go to **APIs & Services → Credentials**
5. Click **+ Create Credentials → API Key**
6. Copy the key (starts with `AIza`)

> Google gives **1,000 free Vision API requests/month**.

---

## Running Locally

### 1. Download the project and enter the folder
```bash
cd little-scholar
```

### 2. Download the CC-CEDICT dictionary (free, one-time)
This file provides English meanings for Chinese characters.
```bash
# Mac/Linux:
curl -L "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz" | gunzip > cedict_ts.u8

# Windows (PowerShell):
Invoke-WebRequest "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz" -OutFile cedict.gz
# Then extract cedict.gz and rename to cedict_ts.u8
```

### 3. Create a virtual environment
```bash
python -m venv venv

# Mac/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Set up your environment variables
```bash
cp .env.example .env
```
Edit `.env` and add your Google Vision key:
```
GOOGLE_VISION_API_KEY=AIzaSy-your-key-here
FLASK_ENV=development
```

### 6. Run the app
```bash
python app.py
```

Open **http://localhost:5000** 🎉

---

## Deploying to Railway (Free Tier)

### 1. Add cedict_ts.u8 to your repo
The dictionary file is ~10MB — it's fine to commit it:
```bash
git add cedict_ts.u8
```

### 2. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/little-scholar.git
git push -u origin main
```

### 3. Deploy on Railway
1. Go to https://railway.app → sign in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your repo — Railway auto-detects Python

### 4. Add environment variable
1. Click your project → **Variables** tab
2. Add: `GOOGLE_VISION_API_KEY` = your key
3. Railway redeploys automatically

### 5. Get your URL
**Settings → Domains → Generate Domain**
→ `little-scholar-production.up.railway.app` 🚀

---

## Deploying to Render (Alternative)

1. Go to https://render.com → **New → Web Service**
2. Connect your GitHub repo
3. Set **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
4. Add `GOOGLE_VISION_API_KEY` in the **Environment** tab
5. Click **Create Web Service**

> Render free tier spins down after 15 min inactivity — first load takes ~30s.

---

## Project Structure

```
little-scholar/
├── app.py              # Flask backend
├── templates/
│   └── index.html      # Full frontend (React via CDN)
├── cedict_ts.u8        # CC-CEDICT dictionary (you download this)
├── requirements.txt
├── Procfile
├── .env.example
└── .env                # Your keys (never commit this!)
```

## How It Works

1. Image upload → browser preprocesses (contrast + resize)
2. `POST /api/ocr` → Google Cloud Vision → extracted Chinese text
3. `POST /api/lookup` → **pypinyin** generates tone-marked pinyin locally, **CC-CEDICT** provides meanings — zero API calls
4. Frontend renders article with pinyin above each character
