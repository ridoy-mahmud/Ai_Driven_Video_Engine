# Deployment Guide

## ⚠️ Why Vercel Does NOT Work

This application **cannot** be deployed on Vercel because:

| Requirement             | This App Needs                 | Vercel Provides                |
| ----------------------- | ------------------------------ | ------------------------------ |
| Long-running processes  | ✅ FastAPI + Streamlit servers | ❌ Serverless functions only   |
| WebSocket support       | ✅ Required by Streamlit       | ❌ Not supported               |
| `ffmpeg` binary         | ✅ Required by moviepy         | ❌ Not available               |
| Persistent file storage | ✅ Videos saved to disk        | ❌ Ephemeral filesystem        |
| Background async tasks  | ✅ Video generation jobs       | ❌ 10–60s max function timeout |
| SQLite database         | ✅ Task history stored         | ❌ No persistent storage       |

---

## ✅ Option 1 — Railway (Recommended, Full Stack)

Railway supports persistent storage, background processes, ffmpeg, and multiple services.

### Steps

1. **Push your code to GitHub** (make sure `config.toml` is gitignored).

2. **Go to [railway.app](https://railway.app)** → New Project → Deploy from GitHub Repo.

3. **Add a Volume** (for SQLite + output videos):
   - Railway Dashboard → your service → Volumes → Add Volume → mount at `/app/data`

4. **Set Environment Variables** in the Railway dashboard:

   | Variable       | Value                                                           |
   | -------------- | --------------------------------------------------------------- |
   | `API_BASE_URL` | Your Railway public domain, e.g. `https://your-app.railway.app` |
   | `LLM_SOURCE`   | `openai` / `gemini` / `deepseek`                                |
   | `LLM_API_KEY`  | Your LLM API key                                                |
   | `LLM_BASE_URL` | Provider base URL                                               |
   | `LLM_MODEL`    | Model name                                                      |
   | `PORT`         | `8000` (for FastAPI)                                            |

5. Railway will use `railway.toml` and `nixpacks.toml` automatically to install `ffmpeg`.

6. **Deploy a second Railway service** for Streamlit:
   - Same repo, different start command:
     ```
     streamlit run web.py --server.port $PORT --server.headless true
     ```
   - Set `API_BASE_URL` to the FastAPI service domain.

---

## ✅ Option 2 — Streamlit Community Cloud (Frontend Only — Free)

Use this if you already have the FastAPI backend hosted elsewhere.

### Steps

1. Push this repo to GitHub.

2. Go to **[share.streamlit.io](https://share.streamlit.io)** → New app.

3. Set:
   - **Repository**: your GitHub repo
   - **Branch**: `main`
   - **Main file path**: `web.py`

4. In **Advanced settings → Secrets**, add:

   ```toml
   API_BASE_URL = "https://your-fastapi-backend.railway.app"
   ```

5. Click **Deploy**.

> **Note**: Streamlit Community Cloud free tier has resource limits. Video generation (ffmpeg / moviepy) will likely fail without a paid tier or a separately hosted backend.

---

## ✅ Option 3 — Render (Alternative to Railway)

1. Push repo to GitHub.

2. Go to **[render.com](https://render.com)** → New → Blueprint.

3. It will detect `render.yaml` automatically and create two services:
   - `ai-video-engine-api` (FastAPI)
   - `ai-video-engine-ui` (Streamlit)

4. Add a **Disk** to the API service (for output videos and SQLite).

5. Set environment variables as listed in Option 1.

---

## Local Development

```bash
# 1. Install system deps (macOS)
brew install ffmpeg

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install Python packages
pip install -r requirements.txt

# 4. Copy and edit config
cp config-template.toml config.toml
# Edit config.toml with your API keys

# 5. Start both services
# Terminal 1 — FastAPI backend
uvicorn app:app --reload

# Terminal 2 — Streamlit frontend
streamlit run web.py
```

Open http://localhost:8501 for the UI and http://localhost:8000/docs for the API.
