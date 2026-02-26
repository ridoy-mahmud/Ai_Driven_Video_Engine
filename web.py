import base64
import datetime
import json
import os
import time

import pandas as pd
import requests
import streamlit as st

from api.schemas import TaskCreate
from schemas.config import LLMSource, MaterialSource, PromptSource, TTSSource, VideoType
from services.tts.edge import EDGE_VOICES
from services.tts.kokoro import KOKORO_VOICES, ALL_KOKORO_VOICES
from utils.config import config
from utils.url import parse_url


# ─────────────────────────────────────────────────────────
#  Custom CSS for Professional UI
# ─────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    .stApp { font-family: 'Inter', sans-serif; }

    /* ── Professional Navbar Pills ── */
    div[data-testid="stPills"] {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        padding: 0.5rem 0.75rem;
        border-radius: 14px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.12);
        margin-bottom: 0.5rem;
    }
    div[data-testid="stPills"] [role="tablist"] {
        gap: 0.25rem;
    }
    div[data-testid="stPills"] button[role="tab"] {
        color: rgba(255,255,255,0.6) !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        border-radius: 10px !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        padding: 0.45rem 0.9rem !important;
        transition: all 0.25s cubic-bezier(.4,0,.2,1) !important;
    }
    div[data-testid="stPills"] button[role="tab"]:hover {
        color: #fff !important;
        background: rgba(255,255,255,0.1) !important;
        border-color: rgba(255,255,255,0.15) !important;
    }
    div[data-testid="stPills"] button[role="tab"][aria-selected="true"],
    div[data-testid="stPills"] button[role="tab"][aria-checked="true"] {
        color: #fff !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        box-shadow: 0 3px 12px rgba(102,126,234,0.4) !important;
        font-weight: 600 !important;
    }

    /* ── Hero Header ── */
    .main-header {
        padding: 3rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
        background-size: cover !important;
        background-position: center !important;
        background-repeat: no-repeat !important;
        position: relative;
        overflow: hidden;
    }
    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 800;
        margin: 0;
        text-shadow: 0 2px 20px rgba(0,0,0,0.5);
        letter-spacing: -0.02em;
    }
    .main-header p {
        font-size: 1.1rem;
        opacity: 0.95;
        margin-top: 0.6rem;
        text-shadow: 0 1px 10px rgba(0,0,0,0.4);
    }

    /* ── Feature Cards ── */
    .feature-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(255,255,255,0.2);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .feature-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }
    .feature-card h3 { margin: 0 0 0.5rem 0; color: #1a1a2e; font-size: 1.1rem; }
    .feature-card p { margin: 0; color: #444; font-size: 0.9rem; line-height: 1.5; }

    /* ── YouTube-Style Video Cards ── */
    .yt-card {
        background: #fff;
        border-radius: 12px;
        overflow: hidden;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        margin-bottom: 1.25rem;
        border: 1px solid #e8e8e8;
    }
    .yt-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 28px rgba(0,0,0,0.12);
    }
    .yt-meta {
        padding: 0.75rem 0.85rem;
        display: flex;
        gap: 0.65rem;
    }
    .yt-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea, #764ba2);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        font-size: 0.75rem;
        font-weight: 700;
        flex-shrink: 0;
        margin-top: 2px;
    }
    .yt-text { flex: 1; min-width: 0; }
    .yt-title {
        font-size: 0.88rem;
        font-weight: 600;
        color: #0f0f0f;
        line-height: 1.3;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        margin: 0 0 0.3rem 0;
    }
    .yt-channel {
        font-size: 0.75rem;
        color: #606060;
        font-weight: 400;
        margin: 0 0 0.15rem 0;
    }
    .yt-stats {
        font-size: 0.72rem;
        color: #909090;
        display: flex;
        align-items: center;
        gap: 0.3rem;
    }
    .yt-stats span { white-space: nowrap; }
    .yt-badge {
        display: inline-block;
        font-size: 0.6rem;
        padding: 0.12rem 0.45rem;
        border-radius: 3px;
        font-weight: 600;
        letter-spacing: 0.03em;
    }
    .yt-badge-completed { background: #e8f5e9; color: #2e7d32; }
    .yt-badge-type { background: #e3f2fd; color: #1565c0; }

    /* Gallery filter bar */
    .gallery-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
        flex-wrap: wrap;
        gap: 0.5rem;
    }
    .gallery-count {
        font-size: 0.85rem;
        color: #606060;
        font-weight: 500;
    }

    /* ── Section Header ── */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 1.5rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid #667eea;
    }
    .section-header h2 { margin: 0; font-size: 1.4rem; color: #1a1a2e; }

    /* ── Activity Items ── */
    .activity-item {
        padding: 0.75rem 1rem;
        border-left: 3px solid #667eea;
        background: #f8f9ff;
        margin-bottom: 0.5rem;
        border-radius: 0 8px 8px 0;
        color: #1a1a2e;
    }

    /* ── Tech Badges ── */
    .tech-badge {
        display: inline-block;
        background: #f0f0f0;
        padding: 0.25rem 0.65rem;
        border-radius: 6px;
        font-size: 0.75rem;
        margin: 0.15rem;
        color: #555;
        font-weight: 500;
    }

    /* ── About Page ── */
    .about-hero {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 60%, #24243e 100%);
        border-radius: 20px;
        padding: 3rem 2.5rem;
        color: #fff;
        text-align: center;
        margin-bottom: 2.5rem;
        position: relative;
        overflow: hidden;
    }
    .about-hero h1 { font-size: 2.4rem; font-weight: 800; margin: 0 0 0.5rem 0; letter-spacing: -0.02em; }
    .about-hero p  { font-size: 1.05rem; opacity: 0.8; max-width: 600px; margin: 0 auto; line-height: 1.6; }

    .how-step {
        background: #fff;
        border-radius: 14px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 0.9rem;
        border: 1px solid #eef0f8;
        display: flex;
        align-items: flex-start;
        gap: 1rem;
        box-shadow: 0 2px 10px rgba(102,126,234,0.07);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .how-step:hover { transform: translateX(6px); box-shadow: 0 6px 24px rgba(102,126,234,0.13); }
    .step-num {
        width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #fff; font-weight: 800; font-size: 1rem;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 3px 10px rgba(102,126,234,0.35);
        margin-top: 2px;
    }
    .step-body h4 { margin: 0 0 0.3rem 0; font-size: 0.95rem; font-weight: 700; color: #1a1a2e; }
    .step-body p  { margin: 0; font-size: 0.82rem; color: #555; line-height: 1.5; }

    .tool-card {
        border-radius: 14px;
        padding: 1.4rem;
        color: #fff;
        margin-bottom: 0.8rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .tool-card:hover { transform: translateY(-4px); box-shadow: 0 12px 32px rgba(0,0,0,0.16); }
    .tool-card h4 { margin: 0 0 0.4rem 0; font-size: 1rem; font-weight: 700; }
    .tool-card p  { margin: 0; font-size: 0.8rem; opacity: 0.88; line-height: 1.5; }
    .tool-badge {
        display: inline-block; background: rgba(255,255,255,0.22);
        border-radius: 6px; font-size: 0.68rem; padding: 0.15rem 0.55rem;
        margin: 0.15rem 0.1rem 0 0; font-weight: 600; letter-spacing: 0.03em;
    }

    .contributor-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        padding: 2.5rem 2rem;
        text-align: center;
        color: #fff;
        box-shadow: 0 10px 40px rgba(102,126,234,0.3);
        margin-top: 1rem;
    }
    .contributor-avatar {
        width: 80px; height: 80px;
        border-radius: 50%;
        background: rgba(255,255,255,0.2);
        border: 3px solid rgba(255,255,255,0.5);
        display: flex; align-items: center; justify-content: center;
        font-size: 2rem; font-weight: 800;
        margin: 0 auto 1rem auto;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .contributor-card h3 { margin: 0 0 0.3rem 0; font-size: 1.5rem; font-weight: 800; letter-spacing: -0.01em; }
    .contributor-card .role { font-size: 0.9rem; opacity: 0.8; margin-bottom: 1rem; }
    .gh-link {
        display: inline-flex; align-items: center; gap: 0.4rem;
        background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.35);
        padding: 0.5rem 1.2rem; border-radius: 8px; color: #fff;
        text-decoration: none; font-size: 0.85rem; font-weight: 600;
        transition: background 0.2s ease;
    }
    .gh-link:hover { background: rgba(255,255,255,0.28); }

    /* ── Footer ── */
    .app-footer {
        text-align: center;
        padding: 2rem 0 1rem 0;
        color: #999;
        font-size: 0.8rem;
        border-top: 1px solid #eee;
        margin-top: 3rem;
    }

    /* ── Centered Professional Loader ── */
    .stSpinner {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
    }
    .stSpinner > div {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        padding: 2.5rem 0 !important;
    }
    .stSpinner > div > span {
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        color: #667eea !important;
        margin-top: 0.5rem !important;
    }
    /* Style the spinner circle */
    .stSpinner > div > svg,
    .stSpinner > div > i {
        color: #667eea !important;
    }

    /* Also center Streamlit's status messages */
    .stStatusWidget {
        display: flex !important;
        justify-content: center !important;
    }

    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
"""

# Navigation items config
NAV_ITEMS = [
    ("Dashboard", "\U0001f4ca", "dashboard"),
    ("Create Video", "\U0001f3ac", "create"),
    ("Tasks", "\U0001f4cb", "tasks"),
    ("Gallery", "\U0001f3a5", "gallery"),
    ("Remix", "\U0001f504", "remix"),
    ("Trending", "\U0001f4f0", "trending"),
    ("Batch", "\u26a1", "batch"),
    ("About", "\u2139\ufe0f", "about"),
]


# ─────────────────────────────────────────────────────────
#  API Client
# ─────────────────────────────────────────────────────────
class TaskAPIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def create_task(self, task_create: TaskCreate) -> requests.Response:
        url = f"{self.base_url}/v1/tasks"
        return requests.post(url, json=task_create.model_dump())

    def get_task_status(self, task_id: str) -> requests.Response:
        url = f"{self.base_url}/v1/tasks/{task_id}"
        return requests.get(url)

    def get_task_list(self, task_date: datetime.date) -> requests.Response:
        url = f"{self.base_url}/v1/tasks/list/{task_date}"
        return requests.get(url)

    def cancel_task(self, task_id: str) -> requests.Response:
        url = f"{self.base_url}/v1/tasks/{task_id}/cancel"
        return requests.post(url)

    def get_queue_status(self) -> requests.Response:
        url = f"{self.base_url}/v1/tasks/queue/status"
        return requests.get(url)


# ─────────────────────────────────────────────────────────
#  Helper Functions
# ─────────────────────────────────────────────────────────
@st.cache_data(ttl="2h")
def get_hot_list():
    url = "https://api.vvhan.com/api/hotlist/all"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def init_session_state():
    defaults = {
        "current_task_name": None,
        "active_nav": "dashboard",
        "form_ideas": [{"Idea": "", "Status": "Pending"} for _ in range(5)],
        "form_running": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def render_navbar():
    """Render a professional top navigation bar using st.pills."""
    # Map keys to display labels
    nav_labels = [f"{emoji} {label}" for label, emoji, _ in NAV_ITEMS]
    nav_keys = [key for _, _, key in NAV_ITEMS]

    active = st.session_state.get("active_nav", "dashboard")
    active_idx = nav_keys.index(active) if active in nav_keys else 0
    active_label = nav_labels[active_idx]

    # Brand header
    st.markdown(
        '<div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.3rem;">'
        '<span style="font-size:1.15rem;font-weight:800;color:#667eea;letter-spacing:-0.02em;">'
        '\u26a1 AI Video Engine</span>'
        '<span style="font-size:0.7rem;color:#999;background:#f0f0f0;padding:0.15rem 0.5rem;'
        'border-radius:4px;font-weight:500;">v2.0</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    selected = st.pills(
        "Navigation",
        nav_labels,
        default=active_label,
        label_visibility="collapsed",
        key="nav_pills",
    )

    # Update active nav based on selection
    if selected:
        selected_idx = nav_labels.index(selected)
        new_key = nav_keys[selected_idx]
        if new_key != active:
            st.session_state.active_nav = new_key
            st.rerun()

    st.markdown("---")


@st.cache_data(ttl=60, show_spinner="Loading tasks...")
def get_all_tasks_for_analytics(_api_client, days: int = 7) -> list:
    """Fetch tasks from the last N days for analytics (cached 60s)."""
    all_tasks = []
    for i in range(days):
        date = datetime.date.today() - datetime.timedelta(days=i)
        try:
            response = _api_client.get_task_list(date)
            if response.status_code == 200:
                tasks = response.json()
                if tasks:
                    all_tasks.extend(tasks)
        except Exception:
            continue
    return all_tasks


@st.cache_data(ttl=60, show_spinner="Loading videos...")
def get_completed_videos(_api_client, days: int = 7) -> list:
    """Get all completed video tasks with their output paths."""
    all_tasks = get_all_tasks_for_analytics(_api_client, days)
    videos = []
    for task in all_tasks:
        if task.get("status") == "completed" and task.get("result"):
            result_path = task["result"]
            if os.path.exists(result_path) and result_path.endswith(".mp4"):
                task_id = task.get("id", 0)
                folder = parse_url("", int(task_id))
                yt_meta = {}
                yt_meta_path = os.path.join(folder, "_youtube_meta.json")
                if os.path.exists(yt_meta_path):
                    try:
                        with open(yt_meta_path, "r", encoding="utf-8") as f:
                            yt_meta = json.load(f)
                    except Exception:
                        pass
                transcript = []
                transcript_path = os.path.join(folder, "_transcript.json")
                if os.path.exists(transcript_path):
                    try:
                        with open(transcript_path, "r", encoding="utf-8") as f:
                            transcript = json.load(f)
                    except Exception:
                        pass
                videos.append({
                    "task_id": task_id,
                    "name": task.get("name", "Untitled"),
                    "path": result_path,
                    "created": task.get("create_time", ""),
                    "yt_meta": yt_meta,
                    "transcript": transcript,
                    "folder": folder,
                })
    return videos


PROMPTS = {
    "Stock Advisor": "You are a senior business consultant who can help me make wise decisions about stock markets, market analysis, and trading strategies. Please provide practical advice based on industry trends, market research, and best practices.",
    "News Reporter": "I want you to act as a journalist. You will report breaking news, write feature stories and opinion pieces, develop research techniques to verify information and uncover sources, follow journalistic ethics, and deliver accurate reporting in your own unique style.",
    "Research Scholar": "I want you to act as a scholar. You will research a topic of my choice and present the findings in the form of a paper or article. Your task is to identify reliable sources, organize material in a well-structured manner, and document it accurately with citations.",
    "Travel Guide": "You are a professional travel guide. Based on the destination I provide, help me create a 2-day travel itinerary. I prefer a relaxed pace with quiet places for simple sightseeing. Include prices for each location.",
    "Creative Novelist": "You are a novelist. Based on the theme I provide, create creative and engaging stories that captivate readers. You may choose any genre. The goal is to write stories with excellent plot lines, compelling characters, and unexpected twists.",
    "Movie Critic": "You are a senior film critic who analyzes movies based on directing style, narrative structure, performances, cinematography, music, and thematic depth. Provide balanced reviews highlighting both strengths and weaknesses.",
    "Character Analyst": "You are a sharp and fair critic who excels at analyzing public figures based on their personality, appearance, and life trajectory. Provide insightful commentary on the person I name.",
}


# ─────────────────────────────────────────────────────────
#  Sidebar Configuration
# ─────────────────────────────────────────────────────────
def render_sidebar():
    """Render the sidebar with navigation and settings."""
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0;">
            <h2 style="margin: 0;">⚡ AI Video Engine</h2>
            <p style="color: #999; font-size: 0.8rem; margin-top: 0.25rem;">Intelligent Video Generation</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # LLM Source Selection
        st.markdown("##### 🤖 AI Model")
        llm_options = {
            "vscode": "🆓 VS Code Copilot (Free)",
            "openai": "🟢 OpenAI GPT-4o",
            "gemini": "🔵 Google Gemini",
            "deepseek": "🟣 DeepSeek",
        }
        llm_source = st.selectbox(
            "Select AI Provider",
            list(llm_options.keys()),
            format_func=lambda x: llm_options[x],
            index=0,
            help="VS Code Copilot is free via bridge. Others require API keys in config.toml",
        )

        if llm_source == "vscode":
            st.success("✅ Free — No API key needed")
        else:
            provider_cfg = getattr(config.llm, llm_source, None)
            placeholder_keys = ("", "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            if provider_cfg and provider_cfg.api_key and provider_cfg.api_key not in placeholder_keys:
                st.success(f"✅ API key configured")
            else:
                st.warning(f"⚠️ Set API key in config.toml → [llm.{llm_source}]")

        st.markdown("---")

        # Prompt Source
        st.markdown("##### 📝 Script Style")
        prompt_source_list = [e.value for e in PromptSource]
        prompt_source = st.selectbox("Prompt Style", prompt_source_list, index=0)

        st.markdown("---")

        # Video Type
        st.markdown("##### 🎬 Video Settings")
        video_type_labels = {
            "reels": "⚡ Reels (12-30s)",
            "short_content": "📱 Short (1-2 min)",
            "mid_content": "📺 Mid (5-10 min)",
        }
        video_type = st.selectbox(
            "Video Type",
            [e.value for e in VideoType],
            index=1,
            format_func=lambda x: video_type_labels.get(x, x),
        )
        default_speed = 1.3 if video_type == "reels" else 1.0
        video_speed = st.slider("Playback Speed", 0.5, 2.5, default_speed, 0.1)

        st.markdown("---")

        # TTS Source
        st.markdown("##### 🗣️ Voice Settings")
        tts_source_list = [e.value for e in TTSSource]
        tts_source = st.selectbox("TTS Engine", tts_source_list)

        selected_voices = None
        tts_speed = None

        if tts_source == TTSSource.edge.value:
            available_languages = list(EDGE_VOICES.keys())
            tts_language = st.selectbox(
                "Language",
                available_languages,
                index=available_languages.index("english") if "english" in available_languages else 0,
            )
            language_voices = EDGE_VOICES.get(tts_language, EDGE_VOICES["english"])
            default_voices = []
            for pref in ["en-US-BrianNeural", "en-US-AriaNeural"]:
                if pref in language_voices:
                    default_voices.append(pref)
            if not default_voices:
                default_voices = language_voices[:2] if len(language_voices) >= 2 else language_voices[:1]
            selected_voices = st.multiselect("Voices", language_voices, default=default_voices)
            if not selected_voices:
                selected_voices = language_voices[:2]
            tts_speed = st.slider("Speech Speed", 0.5, 2.0, 1.1, 0.1)

        elif tts_source == TTSSource.kokoro.value:
            kokoro_category = st.selectbox(
                "Voice Category",
                list(KOKORO_VOICES.keys()),
                format_func=lambda x: x.replace("_", " ").title(),
            )
            category_voices = KOKORO_VOICES.get(kokoro_category, KOKORO_VOICES["american_female"])
            selected_voices = st.multiselect(
                "Kokoro Voices",
                category_voices,
                default=category_voices[:2] if len(category_voices) >= 2 else category_voices[:1],
            )
            if not selected_voices:
                selected_voices = category_voices[:1]
            tts_speed = st.slider("Speech Speed", 0.5, 2.0, 1.0, 0.1)

        st.markdown("---")

        # Material Source
        st.markdown("##### 🖼️ Media Source")
        material_source_labels = {
            "pixabay": "Pixabay",
            "pexels": "Pexels",
            "both": "Both (Pexels + Pixabay)",
            "all": "All Sources (12 with fallback)",
        }
        mat_list = [e.value for e in MaterialSource]
        material_source = st.selectbox(
            "Stock Media",
            mat_list,
            index=mat_list.index("all") if "all" in mat_list else 0,
            format_func=lambda x: material_source_labels.get(x, x),
        )

        # Yuanbao
        use_yuanbao = st.checkbox("Use Search")
        yuanbao_prompt = ""
        if use_yuanbao:
            role = st.selectbox("Role", list(PROMPTS.keys()))
            yuanbao_prompt = "yuanbao" + PROMPTS[role]

        st.markdown("---")
        st.markdown(
            '<div style="text-align:center;opacity:0.5;"><small>AI Video Engine v2.0</small></div>',
            unsafe_allow_html=True,
        )

    return {
        "llm_source": llm_source,
        "prompt_source": prompt_source,
        "video_type": video_type,
        "video_speed": video_speed,
        "tts_source": tts_source,
        "selected_voices": selected_voices,
        "tts_speed": tts_speed,
        "material_source": material_source,
        "yuanbao_prompt": yuanbao_prompt,
    }


# ─────────────────────────────────────────────────────────
#  PAGE: Dashboard
# ─────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def _load_cover_image_b64():
    """Load and cache the cover image as base64 (cached 1h)."""
    cover_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cover", "cover.jpg")
    if os.path.exists(cover_path):
        with open(cover_path, "rb") as img_f:
            return base64.b64encode(img_f.read()).decode()
    return None


def page_dashboard(api_client: TaskAPIClient, settings: dict):
    # Load cover image for hero section
    b64_img = _load_cover_image_b64()
    if b64_img:
        st.markdown(
            f"""
            <div class="main-header" style="
                background: linear-gradient(rgba(15,12,41,0.55), rgba(48,43,99,0.6)),
                    url('data:image/jpeg;base64,{b64_img}');
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
            ">
                <h1>\u26a1 AI Short Video Engine</h1>
                <p>Transform articles, topics &amp; ideas into professional short videos with AI</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="main-header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">' 
            "<h1>\u26a1 AI Short Video Engine</h1>"
            "<p>Transform articles, topics &amp; ideas into professional short videos with AI</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    all_tasks = get_all_tasks_for_analytics(api_client, 7)

    total = len(all_tasks)
    completed = sum(1 for t in all_tasks if t.get("status") == "completed")
    running = sum(1 for t in all_tasks if t.get("status") == "running")
    failed = sum(1 for t in all_tasks if t.get("status") in ("failed", "timeout"))
    pending = sum(1 for t in all_tasks if t.get("status") == "pending")
    success_rate = (completed / total * 100) if total > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Tasks", total, help="Last 30 days")
    c2.metric("Completed", completed, delta=f"{success_rate:.0f}% rate")
    c3.metric("Running", running)
    c4.metric("Pending", pending)
    c5.metric("Failed", failed)

    st.markdown("---")

    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.markdown("### 📈 Analytics Overview")
        if all_tasks:
            df = pd.DataFrame(all_tasks)
            if "create_time" in df.columns:
                df["date"] = pd.to_datetime(df["create_time"]).dt.date
                daily_counts = df.groupby(["date", "status"]).size().reset_index(name="count")
                pivot = daily_counts.pivot_table(
                    index="date", columns="status", values="count", fill_value=0
                )
                # Use column_config with progress bars for a visual table instead of altair charts
                st.markdown("**Tasks by Date**")
                st.dataframe(
                    pivot.reset_index().rename(columns={"date": "Date"}),
                    use_container_width=True,
                    hide_index=True,
                )

            st.markdown("#### Task Status Distribution")
            status_counts = {}
            for t in all_tasks:
                s = t.get("status", "unknown")
                status_counts[s] = status_counts.get(s, 0) + 1
            status_emojis = {"completed": "✅", "running": "🔄", "pending": "⏳", "failed": "❌", "timeout": "⏰"}
            dist_cols = st.columns(min(len(status_counts), 4))
            for idx, (status, count) in enumerate(sorted(status_counts.items(), key=lambda x: -x[1])):
                emoji = status_emojis.get(status, "❓")
                pct = count / total * 100 if total > 0 else 0
                with dist_cols[idx % len(dist_cols)]:
                    st.metric(f"{emoji} {status.title()}", count, delta=f"{pct:.0f}%")
            if total > 0:
                st.progress(completed / total, text=f"Success rate: {completed}/{total} ({success_rate:.0f}%)")
        else:
            st.info("No tasks yet. Create your first video to see analytics!")

    with right_col:
        st.markdown("### 🚀 Quick Actions")
        if st.button("🎬 Create New Video", use_container_width=True, type="primary"):
            st.session_state.active_nav = "create"
            st.rerun()
        if st.button("📋 View All Tasks", use_container_width=True):
            st.session_state.active_nav = "tasks"
            st.rerun()
        if st.button("🎥 Browse Video Gallery", use_container_width=True):
            st.session_state.active_nav = "gallery"
            st.rerun()

        st.markdown("---")
        st.markdown("### ⚙️ Active Configuration")
        llm_labels = {
            "vscode": "VS Code Copilot (Free)",
            "openai": "OpenAI GPT-4o",
            "gemini": "Google Gemini",
            "deepseek": "DeepSeek",
        }
        st.markdown(f"**AI Model:** {llm_labels.get(settings['llm_source'], settings['llm_source'])}")
        st.markdown(f"**TTS Engine:** {settings['tts_source'].title()}")
        st.markdown(f"**Media Source:** {settings['material_source'].title()}")
        st.markdown(f"**Video Type:** {settings['video_type']}")

        st.markdown("---")
        st.markdown("### 🛠️ Tech Stack")
        techs = [
            "FastAPI", "Streamlit", "OpenAI", "Gemini", "DeepSeek",
            "Edge TTS", "FFmpeg", "SQLite", "Pexels", "Pixabay",
        ]
        tech_html = " ".join(f'<span class="tech-badge">{t}</span>' for t in techs)
        st.markdown(tech_html, unsafe_allow_html=True)

    st.markdown("---")

    # Feature showcase
    st.markdown("### ✨ Platform Capabilities")
    features = [
        ("🤖 Smart Content Analysis", "Automatically extracts core information from articles, URLs and topics to generate structured video scripts."),
        ("🎭 Multi-Role Dialogues", "Transforms content into engaging multi-character conversations with distinct voices and personalities."),
        ("🔍 AI Material Matching", "Intelligently matches relevant B-roll footage from 12+ stock video sources based on semantic analysis."),
        ("🗣️ Neural Voice Synthesis", "Supports multiple TTS engines including Edge TTS & Kokoro with 100+ voices across 40+ languages."),
    ]
    feat_cols = st.columns(4)
    for col, (title, desc) in zip(feat_cols, features):
        with col:
            st.markdown(
                f'<div class="feature-card"><h3>{title}</h3><p>{desc}</p></div>',
                unsafe_allow_html=True,
            )

    # Recent activity
    if all_tasks:
        st.markdown("### 🕐 Recent Activity")
        recent = sorted(all_tasks, key=lambda x: x.get("update_time", ""), reverse=True)[:8]
        for task in recent:
            status = task.get("status", "unknown")
            emoji = {"completed": "✅", "running": "🔄", "pending": "⏳", "failed": "❌", "timeout": "⏰"}.get(status, "❓")
            name = task.get("name", "Untitled")[:60]
            time_str = task.get("update_time", "")[:16]
            st.markdown(
                f'<div class="activity-item">{emoji} <strong>{name}</strong>'
                f'<span style="float:right;color:#999;font-size:0.8rem;">{time_str}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="app-footer">'
        "<p>AI Short Video Engine &mdash; Powered by Large Language Models</p>"
        "<p>Supports OpenAI &bull; Google Gemini &bull; DeepSeek &bull; VS Code Copilot</p>"
        "</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
#  PAGE: Create Video
# ─────────────────────────────────────────────────────────
def page_create_video(api_client: TaskAPIClient, settings: dict):
    st.markdown('<div class="section-header"><h2>🎬 Create New Video</h2></div>', unsafe_allow_html=True)
    st.markdown("Enter a **URL**, **topic**, or pick a **template** — AI will generate a professional short video.")

    task_create = TaskCreate(
        name="",
        prompt_source=settings["prompt_source"],
        tts_source=settings["tts_source"],
        material_source=settings["material_source"],
        llm_source=settings["llm_source"],
        tts_voices=settings["selected_voices"],
        tts_speed=settings["tts_speed"],
        video_type=settings["video_type"],
        video_speed=settings["video_speed"],
    )

    tab_url, tab_topic, tab_template = st.tabs(["🔗 From URL", "✏️ From Topic", "📋 Quick Templates"])

    with tab_url:
        st.markdown("Paste an article URL — AI will extract the content and create a video.")
        url_input = st.text_input("Article URL", placeholder="https://example.com/article")
        if st.button("🚀 Generate Video from URL", type="primary", use_container_width=True, key="url_btn"):
            if url_input:
                task_create.name = settings["yuanbao_prompt"] + url_input
                resp = api_client.create_task(task_create)
                if resp.status_code == 200:
                    st.success("✅ Task created! Go to Task Manager to track progress.")
                    st.json(resp.json())
                else:
                    st.error(f"Failed: {resp.text}")
            else:
                st.warning("Please enter a URL")

    with tab_topic:
        st.markdown("Describe a topic — AI will research, write a script, and produce a video.")
        topic_input = st.text_area("Topic or Description", placeholder="e.g., The future of quantum computing", height=120)
        if st.button("🚀 Generate Video from Topic", type="primary", use_container_width=True, key="topic_btn"):
            if topic_input:
                task_create.name = settings["yuanbao_prompt"] + topic_input
                resp = api_client.create_task(task_create)
                if resp.status_code == 200:
                    st.success("✅ Task created!")
                    st.json(resp.json())
                else:
                    st.error(f"Failed: {resp.text}")
            else:
                st.warning("Please enter a topic")

    with tab_template:
        st.markdown("Pick a pre-made topic to get started instantly.")
        templates = {
            "🔬 Science": "Explain CRISPR gene editing technology and its potential to cure genetic diseases — in an engaging, easy-to-understand way",
            "💰 Finance": "Top 5 investing mistakes beginners make and how to avoid them — with practical tips and real examples",
            "🎮 Gaming": "The evolution of open-world gaming from GTA III to GTA VI — what changed and what's next",
            "🧠 Psychology": "5 cognitive biases that affect your daily decisions without you knowing — with real-life examples",
            "🚀 Space": "The James Webb Telescope's most incredible discoveries and what they mean for humanity",
            "🏥 Health": "Intermittent fasting: what the latest science actually says about its benefits and risks",
        }
        for label, template_text in templates.items():
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"**{label}**: {template_text[:80]}...")
            if c2.button("Use", key=f"tpl_{label}", use_container_width=True):
                task_create.name = settings["yuanbao_prompt"] + template_text
                resp = api_client.create_task(task_create)
                if resp.status_code == 200:
                    st.success(f"✅ Task created: {label}")
                else:
                    st.error("Failed to create task")

    st.markdown("---")
    st.markdown("### ⚙️ Current Configuration")
    llm_labels = {"vscode": "VS Code Copilot", "openai": "OpenAI GPT-4o", "gemini": "Google Gemini", "deepseek": "DeepSeek"}
    cc = st.columns(4)
    cc[0].info(f"🤖 **AI:** {llm_labels.get(settings['llm_source'], settings['llm_source'])}")
    cc[1].info(f"🗣️ **TTS:** {settings['tts_source'].title()}")
    cc[2].info(f"🎬 **Type:** {settings['video_type']}")
    cc[3].info(f"📝 **Style:** {settings['prompt_source']}")


# ─────────────────────────────────────────────────────────
#  PAGE: Task Manager
# ─────────────────────────────────────────────────────────
def page_task_manager(api_client: TaskAPIClient, settings: dict):
    st.markdown('<div class="section-header"><h2>📋 Task Manager</h2></div>', unsafe_allow_html=True)

    task_create = TaskCreate(
        name="",
        prompt_source=settings["prompt_source"],
        tts_source=settings["tts_source"],
        material_source=settings["material_source"],
        llm_source=settings["llm_source"],
        tts_voices=settings["selected_voices"],
        tts_speed=settings["tts_speed"],
        video_type=settings["video_type"],
        video_speed=settings["video_speed"],
    )

    col_date, col_refresh = st.columns([3, 1])
    with col_date:
        task_date = st.date_input("📅 Select Date", datetime.date.today())
    with col_refresh:
        st.markdown("<br>", unsafe_allow_html=True)
        auto_refresh = st.checkbox("Auto-refresh", value=False)

    if auto_refresh:
        time.sleep(10)
        st.rerun()

    if not task_date:
        return

    response = api_client.get_task_list(task_date)
    if response.status_code != 200:
        st.error("Failed to retrieve task list")
        return

    tasks = response.json()
    df = pd.DataFrame(tasks) if tasks else pd.DataFrame()

    if df.empty:
        st.info("📭 No tasks for the selected date. Create a new video to get started!")
        return

    # Summary metrics
    sc = df["status"].value_counts().to_dict()
    m = st.columns(5)
    m[0].metric("Total", len(df))
    m[1].metric("✅ Completed", sc.get("completed", 0))
    m[2].metric("🔄 Running", sc.get("running", 0))
    m[3].metric("⏳ Pending", sc.get("pending", 0))
    m[4].metric("❌ Failed", sc.get("failed", 0) + sc.get("timeout", 0))

    st.markdown("---")

    event = st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={"name": st.column_config.LinkColumn(validate=r"^https?://.+$")},
    )

    if not event.selection["rows"]:
        return

    task_data = df.iloc[event.selection["rows"][0]].to_dict()
    task_id = task_data["id"]
    folder = parse_url("", int(task_id))

    st.markdown("---")

    # Action buttons
    with st.expander("📊 Task Details & Actions", expanded=True):
        bcols = st.columns(4)
        with bcols[0]:
            if st.button("🔄 Refresh", use_container_width=True):
                resp = api_client.get_task_status(task_id)
                if resp.status_code == 200:
                    task_data = resp.json()
        with bcols[1]:
            if st.button("🔁 Rerun", use_container_width=True):
                task_create.name = task_data["name"]
                resp = api_client.create_task(task_create)
                st.success("Rerun initiated!") if resp.status_code == 200 else st.error("Failed")
        with bcols[2]:
            if st.button("🚫 Cancel", use_container_width=True):
                resp = api_client.cancel_task(task_id)
                st.success("Cancelled") if resp.status_code == 200 else st.error("Failed")
        with bcols[3]:
            if st.button("🗑️ Reset", use_container_width=True):
                if os.path.isdir(folder):
                    for fn in os.listdir(folder):
                        if fn == "_html.txt":
                            continue
                        fp = os.path.join(folder, fn)
                        if os.path.isfile(fp):
                            os.remove(fp)
                    st.success("Reset!")

        st.json(task_data)

    # Transcript
    transcript_path = os.path.join(folder, "_transcript.json")
    if os.path.exists(transcript_path):
        with st.expander("📜 Dialogue Script"):
            with open(transcript_path, "r", encoding="utf-8") as f:
                st.json(json.load(f))

    # Video result
    if task_data.get("result") and task_data.get("status") == "completed":
        result_path = task_data["result"]
        if os.path.exists(result_path):
            st.markdown("### 🎬 Generated Video")
            st.video(result_path)

            with open(result_path, "rb") as f:
                download_name = f"{task_id}.mp4"
                yt_meta_path = os.path.join(folder, "_youtube_meta.json")
                if os.path.exists(yt_meta_path):
                    try:
                        with open(yt_meta_path, "r", encoding="utf-8") as mf:
                            yt = json.load(mf)
                        title = yt.get("title", "").strip()
                        if title:
                            safe = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:80]
                            download_name = f"{safe}.mp4"
                    except Exception:
                        pass
                st.download_button("⬇️ Download Video", f, download_name, "video/mp4", use_container_width=True)

            yt_meta_path = os.path.join(folder, "_youtube_meta.json")
            if os.path.exists(yt_meta_path):
                with st.expander("📺 YouTube SEO Metadata"):
                    with open(yt_meta_path, "r", encoding="utf-8") as mf:
                        yt = json.load(mf)
                    st.markdown(f"**Title:** {yt.get('title', 'N/A')}")
                    st.markdown(f"**Description:** {yt.get('description', 'N/A')}")
                    st.markdown(f"**Tags:** {yt.get('tags', 'N/A')}")
                    st.markdown(f"**Hashtags:** {yt.get('hashtags', 'N/A')}")
    elif task_data.get("result"):
        st.code(task_data["result"])


# ─────────────────────────────────────────────────────────
#  PAGE: Video Gallery
# ─────────────────────────────────────────────────────────
def _format_time_ago(date_str: str) -> str:
    """Format a date string into a human-readable 'X ago' string."""
    if not date_str:
        return "Unknown"
    try:
        created = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        now = datetime.datetime.now(created.tzinfo) if created.tzinfo else datetime.datetime.now()
        delta = now - created
        if delta.days > 365:
            return f"{delta.days // 365} year{'s' if delta.days // 365 > 1 else ''} ago"
        if delta.days > 30:
            return f"{delta.days // 30} month{'s' if delta.days // 30 > 1 else ''} ago"
        if delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        mins = delta.seconds // 60
        return f"{max(mins, 1)} min{'s' if mins > 1 else ''} ago"
    except Exception:
        return date_str[:10] if len(date_str) >= 10 else date_str


def _get_file_size_mb(path: str) -> str:
    """Return file size in MB as formatted string."""
    try:
        size = os.path.getsize(path)
        return f"{size / (1024 * 1024):.1f} MB"
    except Exception:
        return "--"


def page_video_gallery(api_client: TaskAPIClient, settings: dict):
    # Header
    st.markdown(
        '<div class="section-header"><h2>🎥 Video Gallery</h2></div>',
        unsafe_allow_html=True,
    )

    # ── Filter Bar ──
    f1, f2, f3, f4 = st.columns([2.5, 1, 1, 1])
    with f1:
        search_query = st.text_input(
            "🔍 Search videos",
            placeholder="Search by title, tags...",
            label_visibility="collapsed",
        )
    with f2:
        days_back = st.selectbox(
            "Time Range", [7, 14, 30, 60, 90], index=0,
            format_func=lambda x: f"Last {x} days",
        )
    with f3:
        cols_per_row = st.selectbox("Grid", [2, 3, 4], index=1, format_func=lambda x: f"{x} columns")
    with f4:
        sort_order = st.selectbox("Sort", ["Newest First", "Oldest First"])

    videos = get_completed_videos(api_client, days_back)
    if sort_order == "Oldest First":
        videos.reverse()

    # Apply search filter
    if search_query:
        q = search_query.lower()
        videos = [
            v for v in videos if q in v.get("name", "").lower()
            or q in str(v.get("yt_meta", {}).get("title", "")).lower()
            or q in str(v.get("yt_meta", {}).get("tags", "")).lower()
        ]

    # ── Empty State ──
    if not videos:
        st.markdown(
            '<div style="text-align:center;padding:5rem 2rem;">'
            '<div style="font-size:4rem;margin-bottom:1rem;">🎬</div>'
            '<h3 style="color:#555;margin:0 0 0.5rem 0;">No Videos Found</h3>'
            '<p style="color:#999;max-width:400px;margin:0 auto;">'
            "Create your first AI video or adjust the filters above.")
        if st.button("🎬 Create Your First Video", type="primary", use_container_width=False):
            st.session_state.active_nav = "create"
            st.rerun()
        return

    # ── Results count ──
    st.markdown(
        f'<div class="gallery-count">Showing <strong>{len(videos)}</strong> video{"s" if len(videos) != 1 else ""}</div>',
        unsafe_allow_html=True,
    )

    # ── Video Grid ──
    for i in range(0, len(videos), cols_per_row):
        row_videos = videos[i : i + cols_per_row]
        cols = st.columns(cols_per_row, gap="medium")
        for col_idx, video in enumerate(row_videos):
            with cols[col_idx]:
                vid_title = video.get("yt_meta", {}).get("title") or video.get("name", "Untitled")
                vid_title_short = vid_title[:65] + ("..." if len(vid_title) > 65 else "")
                task_id = video["task_id"]
                created_str = video.get("created", "")
                time_ago = _format_time_ago(created_str)
                file_size = _get_file_size_mb(video["path"])
                avatar_letter = vid_title[0].upper() if vid_title else "V"
                tags_raw = video.get("yt_meta", {}).get("tags", "")
                hashtags = video.get("yt_meta", {}).get("hashtags", "")

                # ── Video Card ──
                st.markdown(f'<div class="yt-card">', unsafe_allow_html=True)

                # Video player
                st.video(video["path"])

                # Metadata row (YouTube style)
                st.markdown(
                    f'<div class="yt-meta">'
                    f'  <div class="yt-avatar">{avatar_letter}</div>'
                    f'  <div class="yt-text">'
                    f'    <p class="yt-title">{vid_title_short}</p>'
                    f'    <p class="yt-channel">AI Video Engine &middot; Task #{task_id}</p>'
                    f'    <div class="yt-stats">'
                    f'      <span>{file_size}</span>'
                    f'      <span>&middot;</span>'
                    f'      <span>{time_ago}</span>'
                    f'      <span>&middot;</span>'
                    f'      <span class="yt-badge yt-badge-completed">Completed</span>'
                    f'    </div>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                st.markdown('</div>', unsafe_allow_html=True)

                # Action buttons
                b1, b2 = st.columns(2)
                with b1:
                    with open(video["path"], "rb") as f:
                        dl_name = f"video_{task_id}.mp4"
                        if video.get("yt_meta", {}).get("title"):
                            safe = "".join(
                                c for c in video["yt_meta"]["title"]
                                if c.isalnum() or c in " -_"
                            ).strip()[:60]
                            dl_name = f"{safe}.mp4"
                        st.download_button(
                            "⬇️ Download", f, dl_name, "video/mp4",
                            key=f"dl_{task_id}", use_container_width=True,
                        )
                with b2:
                    if st.button("📋 Details", key=f"det_{task_id}", use_container_width=True):
                        st.session_state[f"show_{task_id}"] = not st.session_state.get(
                            f"show_{task_id}", False
                        )

                # Expanded Details Panel
                if st.session_state.get(f"show_{task_id}", False):
                    with st.expander("📺 Video Details & SEO", expanded=True):
                        if video.get("yt_meta"):
                            yt = video["yt_meta"]
                            st.markdown(f"**Title:** {yt.get('title', 'N/A')}")
                            if yt.get("description"):
                                st.markdown(f"**Description:** {yt['description'][:200]}{'...' if len(yt.get('description','')) > 200 else ''}")
                            if tags_raw:
                                # Render as pill badges
                                tag_list = [t.strip() for t in str(tags_raw).split(",") if t.strip()]
                                if tag_list:
                                    tags_html = " ".join(
                                        f'<span style="display:inline-block;background:#f0f0f0;padding:0.15rem 0.5rem;'
                                        f'border-radius:4px;font-size:0.72rem;margin:0.1rem;color:#555;">{t}</span>'
                                        for t in tag_list[:15]
                                    )
                                    st.markdown(f"**Tags:** {tags_html}", unsafe_allow_html=True)
                            if hashtags:
                                st.markdown(f"**Hashtags:** {hashtags}")
                        else:
                            st.caption("No SEO metadata available.")
                        if video.get("transcript"):
                            st.markdown("**Script Preview:**")
                            st.json(video["transcript"][:3])


# ─────────────────────────────────────────────────────────
#  PAGE: Video Remix
# ─────────────────────────────────────────────────────────
def page_video_remix(api_client: TaskAPIClient, settings: dict):
    st.markdown('<div class="section-header"><h2>🔄 Video Remix</h2></div>', unsafe_allow_html=True)
    st.markdown("Upload videos and let AI remix them with voiceover, subtitles & YouTube SEO metadata.")

    uploaded_files = st.file_uploader(
        "Upload video(s)",
        type=["mp4", "mov", "avi", "mkv", "webm"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.markdown(
            '<div style="text-align:center;padding:4rem 2rem;background:linear-gradient(135deg,#f5f7fa 0%,#c3cfe2 100%);border-radius:16px;">'
            "<h3>🎬 Upload Videos to Remix</h3>"
            '<p style="color:#666;">Drag and drop or click to browse. AI will analyze and create social-media-ready versions.</p>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    st.info(f"📁 {len(uploaded_files)} file(s) selected")
    prev_cols = st.columns(min(len(uploaded_files), 3))
    for idx, uf in enumerate(uploaded_files[:3]):
        with prev_cols[idx % 3]:
            st.markdown(f"**📹 {uf.name}**")
            st.video(uf)
    if len(uploaded_files) > 3:
        st.caption(f"...and {len(uploaded_files) - 3} more")

    c1, c2 = st.columns(2)
    with c1:
        remix_type = st.selectbox(
            "Output Type",
            [e.value for e in VideoType],
            format_func=lambda x: {"reels": "⚡ Reels", "short_content": "📱 Short", "mid_content": "📺 Mid"}.get(x, x),
            key="remix_type",
        )
    with c2:
        llm_label = {"vscode": "VS Code Copilot", "openai": "OpenAI", "gemini": "Gemini", "deepseek": "DeepSeek"}
        st.info(f"🤖 AI: {llm_label.get(settings['llm_source'], settings['llm_source'])}")

    if not st.button("🚀 Remix All Videos", type="primary", use_container_width=True):
        return

    upload_dir = "./uploads"
    os.makedirs(upload_dir, exist_ok=True)
    results = []
    progress = st.progress(0)
    status_area = st.empty()

    for idx, uf in enumerate(uploaded_files):
        status_area.info(f"Processing {idx + 1}/{len(uploaded_files)}: {uf.name}")
        path = os.path.join(upload_dir, uf.name)
        with open(path, "wb") as f:
            f.write(uf.getbuffer())

        remix_task = TaskCreate(
            name=f"Video Remix: {uf.name}",
            prompt_source="auto",
            tts_source=settings["tts_source"],
            material_source=settings["material_source"],
            llm_source=settings["llm_source"],
            tts_voices=settings["selected_voices"],
            tts_speed=settings["tts_speed"],
            video_type=remix_type,
            video_speed=settings["video_speed"],
            video_upload_path=path,
        )
        resp = api_client.create_task(remix_task)
        if resp.status_code == 200:
            results.append({"File": uf.name, "Task ID": resp.json().get("id", "?"), "Status": "✅ Created"})
        else:
            results.append({"File": uf.name, "Task ID": "-", "Status": "❌ Failed"})
        progress.progress((idx + 1) / len(uploaded_files))

    status_area.success(f"✅ All {len(uploaded_files)} remix tasks created!")
    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    st.info("Go to **Task Manager** to monitor progress.")


# ─────────────────────────────────────────────────────────
#  PAGE: Trending
# ─────────────────────────────────────────────────────────
def page_trending(api_client: TaskAPIClient, settings: dict):
    st.markdown('<div class="section-header"><h2>📰 Trending Topics</h2></div>', unsafe_allow_html=True)
    st.markdown("Browse trending topics and convert them to videos instantly.")

    task_create = TaskCreate(
        name="",
        prompt_source=settings["prompt_source"],
        tts_source=settings["tts_source"],
        material_source=settings["material_source"],
        llm_source=settings["llm_source"],
        tts_voices=settings["selected_voices"],
        tts_speed=settings["tts_speed"],
        video_type=settings["video_type"],
        video_speed=settings["video_speed"],
    )

    hot_list = get_hot_list()
    if not hot_list or not hot_list.get("data"):
        st.warning("Unable to fetch trending topics. Requires internet access.")
        return

    hot_dict = {d["name"]: d["data"] for d in hot_list["data"]}
    selected = st.selectbox("🔥 Select Source", list(hot_dict.keys()))
    data = hot_dict[selected]
    df = pd.DataFrame(data, columns=["index", "title", "url", "hot"])

    event = st.dataframe(
        df,
        height=(min(len(df), 20) + 1) * 35 + 3,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={"url": st.column_config.LinkColumn(display_text="🔗 Open")},
    )

    if not event.selection["rows"]:
        return

    row = df.iloc[event.selection["rows"][0]]
    st.markdown("---")
    st.markdown(f"### Selected: {row['title']}")
    st.markdown(f"**URL:** {row['url']}")
    if st.button("🚀 Convert to Video", type="primary", use_container_width=True):
        task_create.name = settings["yuanbao_prompt"] + row["url"]
        resp = api_client.create_task(task_create)
        st.success("✅ Task created!") if resp.status_code == 200 else st.error("Failed")


# ─────────────────────────────────────────────────────────
#  PAGE: Batch Processing
# ─────────────────────────────────────────────────────────
def page_batch_processing(api_client: TaskAPIClient, settings: dict):
    st.markdown('<div class="section-header"><h2>📋 Batch Processing</h2></div>', unsafe_allow_html=True)
    st.markdown("Upload a CSV or enter ideas manually. Tasks execute serially with automatic retry.")

    # CSV Upload
    st.markdown("#### 📤 Upload CSV")
    csv_file = st.file_uploader("Upload CSV (column: Idea)", type=["csv"], key="batch_csv")
    if csv_file:
        try:
            csv_df = pd.read_csv(csv_file)
            csv_df.columns = [c.strip() for c in csv_df.columns]
            if "Idea" not in csv_df.columns:
                st.error("CSV must have an 'Idea' column.")
            else:
                if "Status" not in csv_df.columns:
                    csv_df["Status"] = "Pending"
                csv_df["Idea"] = csv_df["Idea"].fillna("").astype(str)
                csv_df["Status"] = csv_df["Status"].fillna("Pending").astype(str)
                st.session_state.form_ideas = csv_df[["Idea", "Status"]].to_dict("records")
                st.success(f"✅ Loaded {len(st.session_state.form_ideas)} ideas")
        except Exception as e:
            st.error(f"Error: {e}")

    # Manual Input
    st.markdown("#### ✏️ Manual Input")
    with st.form("batch_form"):
        edited_rows = []
        for i in range(len(st.session_state.form_ideas)):
            cols = st.columns([4, 1])
            iv = st.session_state.form_ideas[i].get("Idea", "")
            sv = st.session_state.form_ideas[i].get("Status", "Pending")
            idea = cols[0].text_input(f"Idea {i + 1}", value=iv, key=f"bi_{i}")
            cols[1].text_input("Status", value=sv, key=f"bs_{i}", disabled=True)
            edited_rows.append({"Idea": idea, "Status": sv})
        if st.form_submit_button("💾 Save Ideas"):
            st.session_state.form_ideas = edited_rows
            st.success("Saved!")

    if st.button("➕ Add Row"):
        st.session_state.form_ideas.append({"Idea": "", "Status": "Pending"})
        st.rerun()

    st.markdown("---")

    if st.button("🚀 Execute All Pending", type="primary", use_container_width=True):
        ideas = st.session_state.form_ideas
        pending = [r for r in ideas if r["Idea"].strip() and r["Status"].lower() not in ("completed", "done")]
        if not pending:
            st.warning("No pending ideas.")
        else:
            bar = st.progress(0)
            status = st.empty()
            done = 0
            for idx, row in enumerate(ideas):
                text = row["Idea"].strip()
                if not text or row["Status"].lower() in ("completed", "done"):
                    continue
                status.info(f"Processing {idx + 1}/{len(ideas)}: {text[:80]}...")
                ideas[idx]["Status"] = "Processing"
                ok = False
                for attempt in range(2):
                    try:
                        t = TaskCreate(
                            name=text,
                            prompt_source=settings["prompt_source"],
                            tts_source=settings["tts_source"],
                            material_source=settings["material_source"],
                            llm_source=settings["llm_source"],
                            tts_voices=settings["selected_voices"],
                            tts_speed=settings["tts_speed"],
                            video_type=settings["video_type"],
                            video_speed=settings["video_speed"],
                        )
                        r = api_client.create_task(t)
                        if r.status_code == 200:
                            ideas[idx]["Status"] = "Completed"
                            ok = True
                            break
                    except Exception:
                        pass
                if not ok:
                    ideas[idx]["Status"] = "Skipped"
                done += 1
                bar.progress(done / len(pending))
            st.session_state.form_ideas = ideas
            status.success(f"✅ Processed {done} tasks!")

    # Batch dashboard
    st.markdown("---")
    st.markdown("#### 📊 Batch Status")
    if st.session_state.form_ideas:
        bdf = pd.DataFrame(st.session_state.form_ideas)
        bdf = bdf[bdf["Idea"].str.strip() != ""]
        if not bdf.empty:
            sc = bdf["Status"].value_counts()
            mc = st.columns(4)
            mc[0].metric("Total", len(bdf))
            mc[1].metric("✅ Done", sum(v for k, v in sc.items() if k.lower() in ("completed", "done")))
            mc[2].metric("⏳ Pending", sum(v for k, v in sc.items() if k.lower() == "pending"))
            mc[3].metric("❌ Failed", sum(v for k, v in sc.items() if "fail" in k.lower() or "skip" in k.lower()))
            st.dataframe(bdf, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────
#  ABOUT PAGE
# ─────────────────────────────────────────────────────────
def page_about(api_client, settings: dict):
    # ── Hero ──────────────────────────────────────────────
    st.markdown(
        '<div class="about-hero">'
        '<div style="font-size:3rem;margin-bottom:0.75rem;">⚡</div>'
        '<h1>AI Short Video Engine</h1>'
        '<p>An end-to-end automated pipeline that turns any article, URL, or topic into a '
        'polished short-form video — powered by LLMs, neural TTS, and smart stock footage selection.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── How It Works ──────────────────────────────────────
    st.markdown("## 🚀 How It Works")
    st.markdown("Follow these 6 steps to generate a professional AI video in minutes:")
    steps = [
        ("1", "Provide Input",
         "Paste an article URL, enter a topic, or pick a trending item. "
         "The engine accepts raw text, links, or CSV batch files."),
        ("2", "AI Script Generation",
         "A large language model (VS Code Copilot / OpenAI / Gemini / DeepSeek) reads the content "
         "and writes a multi-role dialogue script tailored to your chosen video style."),
        ("3", "Neural Voice Synthesis",
         "Each dialogue line is converted to natural speech using Edge TTS or Kokoro TTS. "
         "Different characters get different voices for an engaging back-and-forth flow."),
        ("4", "Smart Footage Matching",
         "The engine extracts semantic keywords from the script and searches 12+ stock media "
         "sources (Pexels, Pixabay, and more) to find the most relevant B-roll clips."),
        ("5", "Video Assembly",
         "FFmpeg combines the voice tracks, stock footage, and auto-generated captions into a "
         "single ready-to-publish MP4 optimised for Reels, YouTube Shorts, or longer formats."),
        ("6", "SEO Metadata",
         "The LLM also generates a YouTube title, description, tags, and hashtags straight after "
         "rendering, so you can upload immediately without any extra work."),
    ]
    for num, title, desc in steps:
        st.markdown(
            f'<div class="how-step">'
            f'<div class="step-num">{num}</div>'
            f'<div class="step-body"><h4>{title}</h4><p>{desc}</p></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Pages & Tools ─────────────────────────────────────
    st.markdown("## 🧭 Pages & What They Do")
    tools = [
        (
            "📊 Dashboard",
            "Your command centre. See real-time task metrics, a success-rate progress bar, "
            "recent activity feed, platform feature highlights, and quick-action shortcuts — all at a glance.",
            "linear-gradient(135deg,#667eea 0%,#764ba2 100%)",
            ["Analytics", "Quick Actions", "Activity Feed"],
        ),
        (
            "🎬 Create Video",
            "Three creation modes: paste a URL for automatic article extraction, describe a topic "
            "from scratch, or choose a one-click template. Combines with your sidebar LLM & voice settings.",
            "linear-gradient(135deg,#f093fb 0%,#f5576c 100%)",
            ["URL Input", "Topic Mode", "Templates"],
        ),
        (
            "📋 Task Manager",
            "Monitor every task by date. View live status, inspect the dialogue transcript, "
            "watch the rendered video, download it, or cancel/rerun tasks with one click.",
            "linear-gradient(135deg,#4facfe 0%,#00f2fe 100%)",
            ["Live Status", "Download", "Cancel / Rerun"],
        ),
        (
            "🎥 Video Gallery",
            "A YouTube-style grid of every completed video. Search by title or tags, "
            "filter by date range, choose 2-4 columns, and expand each card for full SEO metadata.",
            "linear-gradient(135deg,#43e97b 0%,#38f9d7 100%)",
            ["Search", "SEO Metadata", "Download"],
        ),
        (
            "🔄 Video Remix",
            "Upload your own footage and let the AI add a voiceover, generate subtitles, "
            "and create YouTube SEO metadata automatically — great for repurposing existing content.",
            "linear-gradient(135deg,#fa709a 0%,#fee140 100%)",
            ["Upload Video", "AI Voiceover", "Auto Subtitles"],
        ),
        (
            "📰 Trending",
            "Live hot-list from 20+ platforms. Select any trending headline and convert it into "
            "a video with a single click — perfect for topical, fast-turnaround content.",
            "linear-gradient(135deg,#a18cd1 0%,#fbc2eb 100%)",
            ["Live Feed", "One-Click Convert", "20+ Sources"],
        ),
        (
            "⚡ Batch Processing",
            "Upload a CSV of ideas or enter them manually. The engine processes each row serially "
            "with automatic retry on failure, showing a live progress bar as it works through the queue.",
            "linear-gradient(135deg,#f7971e 0%,#ffd200 100%)",
            ["CSV Upload", "Auto Retry", "Progress Bar"],
        ),
    ]
    rows = [tools[i:i + 2] for i in range(0, len(tools), 2)]
    for row in rows:
        cols = st.columns(len(row), gap="medium")
        for col, (page_name, desc, gradient, badges) in zip(cols, row):
            with col:
                badge_html = " ".join(
                    f'<span class="tool-badge">{b}</span>' for b in badges
                )
                st.markdown(
                    f'<div class="tool-card" style="background:{gradient};">'
                    f'<h4>{page_name}</h4><p>{desc}</p>'
                    f'<div style="margin-top:0.75rem;">{badge_html}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # ── Tech Stack ────────────────────────────────────────
    st.markdown("## 🛠️ Tech Stack")
    tech_groups = {
        "🤖 AI / LLM": ["OpenAI GPT-4o", "Google Gemini", "DeepSeek", "VS Code Copilot"],
        "🗣️ Voice Synthesis": ["Edge TTS", "Kokoro TTS", "100+ Voices", "40+ Languages"],
        "🖼️ Media Sources": ["Pexels", "Pixabay", "12+ Providers", "Semantic Matching"],
        "⚙️ Backend": ["FastAPI", "SQLite", "SQLAlchemy", "Uvicorn"],
        "🎬 Video Pipeline": ["FFmpeg", "Auto Subtitles", "MP4 Output"],
        "🌐 Frontend": ["Streamlit", "Custom CSS", "Inter Font"],
    }
    tech_cols = st.columns(3)
    for idx, (group, items) in enumerate(tech_groups.items()):
        with tech_cols[idx % 3]:
            badges = " ".join(
                f'<span style="display:inline-block;background:#f0f0f0;padding:0.2rem 0.55rem;'
                f'border-radius:6px;font-size:0.72rem;margin:0.15rem;color:#555;font-weight:500;">{item}</span>'
                for item in items
            )
            st.markdown(
                f'<div style="background:#fff;border:1px solid #eee;border-radius:12px;'
                f'padding:1rem 1.1rem;margin-bottom:0.8rem;box-shadow:0 2px 8px rgba(0,0,0,0.05);">'
                f'<p style="margin:0 0 0.5rem 0;font-weight:700;font-size:0.9rem;color:#1a1a2e;">{group}</p>'
                f'{badges}</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Contributor Spotlight ─────────────────────────────
    st.markdown("## 👨‍💻 Built By")
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(
            '<div class="contributor-card">'
            '<div class="contributor-avatar">R</div>'
            '<h3>Ridoy Mahmud</h3>'
            '<p class="role">Full-Stack AI Developer &nbsp;&middot;&nbsp; ML Engineer</p>'
            '<p style="font-size:0.82rem;opacity:0.75;margin-bottom:1.25rem;line-height:1.6;">'
            'Designed and built the entire AI Short Video Engine — from the LLM pipeline and '
            'TTS integration to the video assembly system and this interactive Streamlit interface.'
            '</p>'
            '<a class="gh-link" href="https://github.com/ridoy-mahmud" target="_blank">'
            '&#x1F4BB;&nbsp; github.com/ridoy-mahmud'
            '</a>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="app-footer">'
        "<p>AI Short Video Engine &mdash; Powered by Large Language Models</p>"
        "<p>Supports OpenAI &bull; Google Gemini &bull; DeepSeek &bull; VS Code Copilot</p>"
        '</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="AI Short Video Engine",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    init_session_state()

    settings = render_sidebar()

    # Professional top navigation bar
    render_navbar()

    page_map = {
        "dashboard": page_dashboard,
        "create": page_create_video,
        "tasks": page_task_manager,
        "gallery": page_video_gallery,
        "remix": page_video_remix,
        "trending": page_trending,
        "batch": page_batch_processing,
        "about": page_about,
    }

    active = st.session_state.get("active_nav", "dashboard")
    handler = page_map.get(active, page_dashboard)
    handler(api_client, settings)


# ─────────────────────────────────────────────────────────
#  Embedded FastAPI backend — used on Streamlit Community Cloud
#  (starts uvicorn in a background thread so both services run
#   in a single process without needing Railway / Render).
# ─────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Starting backend server…")
def _start_backend_server() -> bool:
    """Launch the FastAPI app in a daemon thread and wait until it is ready.

    Returns True on success, False on timeout.
    Decorated with st.cache_resource so it is called only once per process.
    """
    import threading
    import uvicorn
    from app import app as _fastapi_app

    port = config.api.app_port

    def _run():
        uvicorn.run(_fastapi_app, host="127.0.0.1", port=port, log_level="error")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # Poll until the backend accepts connections (max 45 s)
    for _ in range(45):
        try:
            requests.get(f"http://127.0.0.1:{port}/v1/tasks/queue/status", timeout=1)
            return True
        except Exception:
            time.sleep(1)
    return False  # timed out — API calls will fail gracefully in the UI


# Use API_BASE_URL env var when deployed (Railway, Render, Streamlit Cloud).
# Falls back to localhost for local development.
_default_base = f"http://localhost:{config.api.app_port}"
base_url = os.environ.get("API_BASE_URL", _default_base).rstrip("/")

# When no external backend URL is configured, start the embedded backend.
if not os.environ.get("API_BASE_URL"):
    _start_backend_server()

api_client = TaskAPIClient(base_url)

if __name__ == "__main__":
    main()
