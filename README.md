<div align="center">
  <h1>⚡ AI Short Video Engine</h1>
  <p><strong>Transform articles, topics &amp; ideas into professional short videos with AI</strong></p>
  <p>
    <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/Streamlit-1.45-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
  <p>
    <a href="#-quick-start">Quick Start</a> •
    <a href="#-features">Features</a> •
    <a href="#-supported-ai-models">AI Models</a> •
    <a href="#-screenshots">Screenshots</a> •
    <a href="#-configuration">Configuration</a> •
    <a href="#-contributing">Contributing</a>
  </p>
</div>

---

## 📖 Overview

**AI Short Video Engine** is a full-stack AI-powered platform that converts any article URL, text topic, or uploaded video into high-quality short videos — complete with multi-character voiceover, subtitles, B-roll footage, and YouTube SEO metadata.

Built with **FastAPI** + **Streamlit**, it features a modern dashboard with real-time analytics, a video gallery, batch processing, and support for **4 LLM providers** (VS Code Copilot, OpenAI, Google Gemini, DeepSeek).

### What it does

1. **Input** → Paste a URL, describe a topic, or upload a video
2. **AI Processing** → LLM generates a multi-character dialogue script
3. **Voice Synthesis** → Edge TTS or Kokoro creates natural voiceover
4. **B-Roll Matching** → AI searches 12+ stock video sources for relevant footage
5. **Video Production** → FFmpeg assembles the final video with subtitles & transitions
6. **Output** → Download the video + YouTube SEO title, description, tags & hashtags

---

## ✨ Features

| Feature                    | Description                                                    |
| -------------------------- | -------------------------------------------------------------- |
| 🤖 **Multi-LLM Support**   | VS Code Copilot (free), OpenAI GPT-4o, Google Gemini, DeepSeek |
| 📊 **Analytics Dashboard** | Real-time task metrics, charts, success rates, recent activity |
| 🎥 **Video Gallery**       | Browse all generated videos in a 3-column grid with filters    |
| 🎭 **50+ Script Styles**   | Tech talk, true crime, podcast, debate, comedy roast, and more |
| 🗣️ **100+ AI Voices**      | Edge TTS (40+ languages) and Kokoro (local, no API key)        |
| 🔍 **12+ B-Roll Sources**  | Pexels, Pixabay, and smart fallback across multiple providers  |
| 🔄 **Video Remix**         | Upload existing videos → AI analyzes & creates new versions    |
| 📋 **Batch Processing**    | CSV upload or manual entry for bulk video generation           |
| 📰 **Trending Topics**     | Browse trending articles and convert to videos in one click    |
| 📺 **YouTube SEO**         | Auto-generates optimized titles, descriptions, tags & hashtags |

---

## 🤖 Supported AI Models

| Provider            | Model                | Cost                                 | Setup                        |
| ------------------- | -------------------- | ------------------------------------ | ---------------------------- |
| **VS Code Copilot** | GPT-4o via bridge    | **Free** (with Copilot subscription) | Default — no config needed   |
| **OpenAI**          | GPT-4o / GPT-4o-mini | Pay-per-use                          | Add API key to `config.toml` |
| **Google Gemini**   | Gemini 2.0 Flash     | Free tier available                  | Add API key to `config.toml` |
| **DeepSeek**        | DeepSeek Chat        | Pay-per-use                          | Add API key to `config.toml` |

The default is **VS Code Copilot** (free). Switch providers anytime from the sidebar dropdown.

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **FFmpeg** — installed and on system PATH
- **ImageMagick** — for image processing (optional)
- **Git**

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/AI-Short-Video-Engine.git
cd AI-Short-Video-Engine

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy the template
cp config-template.toml config.toml
```

Edit `config.toml` and configure your preferred AI provider:

```toml
[llm]
llm_source = "vscode"  # Options: "vscode", "openai", "gemini", "deepseek"

# Free option — works out of the box with VS Code Copilot
[llm.vscode]
api_key = "vscode-bridge"
base_url = "http://127.0.0.1:5199/v1"
model = "copilot-chat"

# OpenAI (optional)
[llm.openai]
api_key = "sk-your-openai-key"
base_url = "https://api.openai.com/v1"
model = "gpt-4o-mini"

# Google Gemini (optional)
[llm.gemini]
api_key = "your-gemini-key"
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
model = "gemini-2.0-flash"

# DeepSeek (optional)
[llm.deepseek]
api_key = "sk-your-deepseek-key"
base_url = "https://api.deepseek.com"
model = "deepseek-chat"
```

Also configure at least one stock media API key:

```toml
[material.pexels]
api_key = "your-pexels-key"  # Get free at https://www.pexels.com/api/

[material.pixabay]
api_key = "your-pixabay-key"  # Get free at https://pixabay.com/api/docs/
```

### Run

```bash
# Terminal 1: Start the backend API
python app.py

# Terminal 2: Launch the web UI
streamlit run web.py --server.port 8001
```

Open **http://localhost:8001** in your browser.

### Command Line (optional)

```bash
# Convert an article URL to video
python main.py https://example.com/article
```

---

## 📸 Screenshots

### Dashboard

The main dashboard shows real-time analytics, task metrics, quick actions, and recent activity.

### Create Video

Three input methods: URL, topic description, or quick templates for instant video generation.

### Video Gallery

Browse all generated videos in a responsive grid with download buttons and metadata.

### Task Manager

Monitor all tasks with status tracking, auto-refresh, video preview, and YouTube SEO data.

---

## 📂 Project Structure

```
AI-Short-Video-Engine/
├── app.py                  # FastAPI backend entry point
├── web.py                  # Streamlit frontend (dashboard, gallery, etc.)
├── main.py                 # CLI entry point
├── config-template.toml    # Configuration template (copy to config.toml)
├── requirements.txt        # Python dependencies
│
├── api/                    # REST API layer
│   ├── router.py           # API route definitions
│   ├── service.py          # Task processing service
│   ├── crud.py             # Database operations
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic request/response schemas
│   └── database.py         # Database configuration
│
├── schemas/                # Data model definitions
│   ├── config.py           # App configuration models (LLM, TTS, Video, etc.)
│   └── video.py            # Video transcript and material models
│
├── services/               # Core services
│   ├── llm.py              # LLM client (OpenAI-compatible)
│   ├── llm_bridge.py       # VS Code Copilot bridge server
│   ├── video.py            # Video generation pipeline
│   ├── yuanbao.py          # Yuanbao search integration
│   ├── material/           # Stock video/image providers
│   │   ├── pexels.py       # Pexels API
│   │   └── pixabay.py      # Pixabay API
│   └── tts/                # Text-to-speech engines
│       ├── edge.py         # Microsoft Edge TTS (free, 100+ voices)
│       └── kokoro.py       # Kokoro local TTS (no API key)
│
├── utils/                  # Utility modules
│   ├── config.py           # Config loading & management
│   ├── video.py            # FFmpeg video assembly
│   ├── subtitle.py         # Subtitle rendering
│   ├── text.py             # Text processing
│   ├── url.py              # URL parsing & content extraction
│   └── log.py              # Logging setup
│
├── prompts/                # 50+ prompt templates for different styles
├── fonts/                  # Font files for subtitles
├── resource/               # Static resources (BGM, etc.)
└── vscode-llm-bridge/      # VS Code extension for LLM bridge
```

---

## 🛠️ Tech Stack

| Component    | Technology                                            |
| ------------ | ----------------------------------------------------- |
| **Backend**  | FastAPI, SQLAlchemy, SQLite                           |
| **Frontend** | Streamlit with custom CSS                             |
| **AI / LLM** | OpenAI SDK (compatible with GPT-4o, Gemini, DeepSeek) |
| **Voice**    | Microsoft Edge TTS, Kokoro ONNX                       |
| **Video**    | FFmpeg, MoviePy, Pillow                               |
| **Media**    | Pexels API, Pixabay API                               |

---

## ⚙️ Configuration Reference

### LLM Providers

| Setting                | Description           | Default           |
| ---------------------- | --------------------- | ----------------- |
| `llm.llm_source`       | Active LLM provider   | `"vscode"`        |
| `llm.vscode.api_key`   | VS Code bridge key    | `"vscode-bridge"` |
| `llm.openai.api_key`   | OpenAI API key        | `""`              |
| `llm.gemini.api_key`   | Google Gemini API key | `""`              |
| `llm.deepseek.api_key` | DeepSeek API key      | `""`              |

### TTS Engines

| Engine   | API Key Required | Languages | Voices |
| -------- | ---------------- | --------- | ------ |
| Edge TTS | No (free)        | 40+       | 100+   |
| Kokoro   | No (local)       | English   | 20+    |

### Video Settings

| Setting        | Description       | Default |
| -------------- | ----------------- | ------- |
| `video.fps`    | Frames per second | `24`    |
| `video.width`  | Video width       | `1080`  |
| `video.height` | Video height      | `1920`  |

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** this repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to your branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### Development Setup

```bash
git clone https://github.com/YOUR_USERNAME/AI-Short-Video-Engine.git
cd AI-Short-Video-Engine
python -m venv .venv
.venv\Scripts\activate  # or source .venv/bin/activate
pip install -r requirements.txt
cp config-template.toml config.toml
# Edit config.toml with your API keys
python app.py  # Start backend
# In another terminal:
streamlit run web.py --server.port 8001
```

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Inspired by [NotebookLlama](https://github.com/meta-llama/llama-cookbook/tree/main/end-to-end-use-cases/NotebookLlama)
- [Pexels](https://www.pexels.com/) and [Pixabay](https://pixabay.com/) for stock media APIs
- [Edge TTS](https://github.com/rany2/edge-tts) for free neural voice synthesis
- Built with [FastAPI](https://fastapi.tiangolo.com/), [Streamlit](https://streamlit.io/), and [FFmpeg](https://ffmpeg.org/)

---

<div align="center">
  <p>Made with ❤️ for the AI & content creation community</p>
  <p>If you find this useful, please ⭐ star the repo!</p>
</div>
