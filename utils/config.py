import os
import sys
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import toml as _toml_fallback

from schemas.config import Config, PromptConfig, PromptSource

# ─── Default material search-term prompt (kept here so it doesn't need to be in env) ───
_MATERIAL_PROMPT = """### Role: Cinematic B-Roll Video Search Term Generator

#### Goal:
You are a professional video editor. Given a JSON array of script paragraphs, generate **highly visual, concrete, and stock-video-friendly** English search terms for each paragraph.

#### Critical Rules:
1. Each paragraph gets **8 search terms** — from most specific to most generic.
2. Terms MUST describe **visual scenes, objects, or actions** — NOT abstract concepts.
3. Use **1-3 English words** per term.
4. Output ONLY the JSON — no explanations, no markdown.

#### Output Format:
[
  {"id": 1, "search_terms": ["term1", "term2", "term3", "term4", "term5", "term6", "term7", "term8"]},
  {"id": 2, "search_terms": ["term1", "term2", "term3", "term4", "term5", "term6", "term7", "term8"]}
]
"""


def _build_config_from_env() -> dict:
    """Build a full config dict from environment variables or Streamlit secrets.

    Called automatically when ``config.toml`` is not present on disk (e.g.
    Streamlit Community Cloud where the file is gitignored).
    """

    # ── Read Streamlit secrets if available ──
    _secrets: dict = {}
    try:
        import streamlit as st  # noqa: PLC0415
        _secrets = dict(st.secrets)
    except Exception:
        pass

    def _get(key: str, default: str = "") -> str:
        return os.environ.get(key) or str(_secrets.get(key, default))

    llm_source = _get("LLM_SOURCE", "openai")
    api_key = _get("LLM_API_KEY") or _get("OPENAI_API_KEY")

    return {
        "llm": {
            "llm_source": llm_source,
            "api_key": api_key,
            "base_url": _get("LLM_BASE_URL", "https://api.openai.com/v1"),
            "model": _get("LLM_MODEL", "gpt-4o-mini"),
            "source": _get("PROMPT_SOURCE", "tech_talk"),
            "vscode": {
                "api_key": "vscode-bridge",
                "base_url": "http://127.0.0.1:5199/v1",
                "model": "copilot-chat",
            },
            "openai": {
                "api_key": _get("OPENAI_API_KEY") or api_key,
                "base_url": "https://api.openai.com/v1",
                "model": _get("LLM_MODEL", "gpt-4o-mini"),
            },
            "gemini": {
                "api_key": _get("GEMINI_API_KEY") or api_key,
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "model": _get("GEMINI_MODEL", "gemini-2.0-flash"),
            },
            "deepseek": {
                "api_key": _get("DEEPSEEK_API_KEY") or api_key,
                "base_url": "https://api.deepseek.com",
                "model": _get("DEEPSEEK_MODEL", "deepseek-chat"),
            },
        },
        "yuanbao": {
            "base_url": "http://localhost:8082/v1/",
            "api_key": "",
            "model": "deepseek-r1-search",
            "hy_user": "",
            "agent_id": "naQivTmsDa",
            "chat_id": "",
            "should_remove_conversation": False,
        },
        "tts": {
            "source": _get("TTS_SOURCE", "edge"),
            "edge": {
                "voices": [
                    _get("TTS_VOICE_1", "en-US-AriaNeural"),
                    _get("TTS_VOICE_2", "en-US-DavisNeural"),
                ],
                "speed": float(_get("TTS_SPEED", "1.1")),
            },
        },
        "video": {
            "fps": 24,
            "background_audio": "",
            "width": 1080,
            "height": 1920,
            "title": {
                "font": "./fonts/DreamHanSans-W20.ttc",
                "width_ratio": 0.8,
                "font_size_ratio": 12,
                "position_ratio": 0.5,
                "color": "white",
                "stroke_color": "black",
                "stroke_width": 2,
                "text_align": "center",
                "duration": 0.5,
            },
            "subtitle": {
                "font": "./fonts/DreamHanSans-W20.ttc",
                "width_ratio": 0.8,
                "font_size_ratio": 17,
                "position_ratio": 0.667,
                "color": "white",
                "stroke_color": "black",
                "stroke_width": 1,
                "text_align": "center",
                "interval": 0.2,
            },
        },
        "api": {
            "database_url": "sqlite+aiosqlite:///tasks.db",
            "app_port": int(_get("API_PORT", "8000")),
            "max_concurrent_tasks": int(_get("MAX_CONCURRENT_TASKS", "1")),
            "task_timeout_seconds": int(_get("TASK_TIMEOUT", "600")),
        },
        "material": {
            "source": _get("MATERIAL_SOURCE", "pexels"),
            "minimum_duration": 3,
            "prompt": _MATERIAL_PROMPT,
            "pexels": {
                "api_key": _get("PEXELS_API_KEY", ""),
                "locale": "en-US",
            },
            "pixabay": {
                "api_key": _get("PIXABAY_API_KEY", ""),
                "lang": "en",
                "video_type": "all",
            },
        },
    }


# Mapping of prompt sources to descriptive labels for auto-selection
PROMPT_DESCRIPTIONS = {
    "podcast": "General podcast format, conversational tone",
    "crosstalk": "Chinese crosstalk comedy format",
    "talkshow": "Talk show format with humor",
    "tech_talk": "Technology discussion, gadgets, software, AI",
    "true_crime": "True crime, mystery, investigation",
    "science_explainer": "Science explanation, discovery, research",
    "motivation": "Motivational, self-improvement, success stories",
    "business_strategy": "Business, entrepreneurship, strategy",
    "personal_finance": "Money, investing, savings, budgets",
    "health_wellness": "Health, fitness, diet, wellness",
    "history_stories": "Historical events, people, civilizations",
    "psychology": "Psychology, behavior, mental processes",
    "debate": "Debate format, pros and cons, arguments",
    "comedy_roast": "Comedy roast, humor, satire",
    "study_guide": "Educational study guide, learning tips",
    "storytelling": "Narrative storytelling, fiction, tales",
    "ai_future": "AI, future technology, automation",
    "relationship_advice": "Relationships, dating, love advice",
    "crypto_blockchain": "Cryptocurrency, blockchain, Web3",
    "sports_analysis": "Sports analysis, games, athletes",
    "food_cooking": "Food, cooking, recipes, cuisine",
    "travel_adventure": "Travel, destinations, adventure",
    "movie_review": "Movie reviews, film analysis",
    "horror_mystery": "Horror, mystery, suspense",
    "startup_hustle": "Startup culture, hustle, entrepreneurship",
    "philosophy": "Philosophy, deep thinking, existence",
    "gaming": "Gaming, video games, esports",
    "climate_environment": "Climate change, environment, sustainability",
    "space_cosmos": "Space, astronomy, cosmos, NASA",
    "career_growth": "Career advice, professional growth",
    "diy_hacks": "DIY projects, life hacks",
    "music_analysis": "Music analysis, artists, genres",
    "parenting": "Parenting, child development",
    "fashion_style": "Fashion, style, trends",
    "legal_explainer": "Legal topics, law explained simply",
    "social_media": "Social media strategy, growth",
    "pet_animals": "Pets, animals, wildlife",
    "habits_improvement": "Habits, productivity, self-improvement",
    "real_estate": "Real estate, housing, property",
    "education_learning": "Education, learning methods",
    "pop_mysteries": "Pop culture mysteries, conspiracies",
    "mental_health": "Mental health, anxiety, coping",
    "did_you_know": "Fun facts, trivia, did you know",
}


def load_config(config_file: str = "config.toml") -> dict:
    # When the primary config file is absent (e.g. Streamlit Cloud where config.toml
    # is gitignored), build the config from environment variables / Streamlit secrets.
    if config_file == "config.toml" and not os.path.exists(config_file):
        return _build_config_from_env()

    if sys.version_info >= (3, 11):
        with open(config_file, "rb") as f:
            config = tomllib.load(f)
    else:
        with open(config_file, "r", encoding="utf-8") as f:
            config = _toml_fallback.load(f)
    return config


def get_prompt_config(prompt_source: Optional[str] = None) -> PromptConfig:
    # 'auto' is handled separately in services/video.py before calling this
    if prompt_source == "auto":
        prompt_source = "science_explainer"  # Fallback if auto-selection didn't run
    
    config_mapping = {k.value: f"./prompts/{k.value}.toml" for k in PromptSource if k.value != "auto"}
    default_config_path = "./prompts/podcast.toml"
    config_path = config_mapping.get(prompt_source, default_config_path)

    try:
        config = load_config(config_path)
    except Exception as e:
        raise RuntimeError(f"Failed to load config from {config_path}: {e}")

    return PromptConfig.model_validate(config)


_cfg = load_config()
config = Config.model_validate(_cfg)
api_config = config.api
