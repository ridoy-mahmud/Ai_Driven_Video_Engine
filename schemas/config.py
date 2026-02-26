from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class PromptSource(str, Enum):
    auto = "auto"  # LLM auto-selects the best prompt based on content
    # Chinese prompts
    podcast = "podcast"
    crosstalk = "crosstalk"
    talkshow = "talkshow"
    # English prompts
    tech_talk = "tech_talk"
    true_crime = "true_crime"
    science_explainer = "science_explainer"
    motivation = "motivation"
    business_strategy = "business_strategy"
    personal_finance = "personal_finance"
    health_wellness = "health_wellness"
    history_stories = "history_stories"
    psychology = "psychology"
    debate = "debate"
    comedy_roast = "comedy_roast"
    study_guide = "study_guide"
    storytelling = "storytelling"
    ai_future = "ai_future"
    relationship_advice = "relationship_advice"
    crypto_blockchain = "crypto_blockchain"
    sports_analysis = "sports_analysis"
    food_cooking = "food_cooking"
    travel_adventure = "travel_adventure"
    movie_review = "movie_review"
    horror_mystery = "horror_mystery"
    startup_hustle = "startup_hustle"
    philosophy = "philosophy"
    gaming = "gaming"
    climate_environment = "climate_environment"
    space_cosmos = "space_cosmos"
    career_growth = "career_growth"
    diy_hacks = "diy_hacks"
    music_analysis = "music_analysis"
    parenting = "parenting"
    fashion_style = "fashion_style"
    legal_explainer = "legal_explainer"
    social_media = "social_media"
    pet_animals = "pet_animals"
    habits_improvement = "habits_improvement"
    real_estate = "real_estate"
    education_learning = "education_learning"
    pop_mysteries = "pop_mysteries"
    mental_health = "mental_health"
    did_you_know = "did_you_know"


class VideoType(str, Enum):
    reels = "reels"                # 12-30 seconds, fast-paced
    short_content = "short_content" # 1-2 minutes
    mid_content = "mid_content"     # 5-10 minutes


class TTSSource(str, Enum):
    edge = "edge"
    kokoro = "kokoro"


class LLMSource(str, Enum):
    vscode = "vscode"
    openai = "openai"
    gemini = "gemini"
    deepseek = "deepseek"


class MaterialSource(str, Enum):
    pixabay = "pixabay"
    pexels = "pexels"
    both = "both"  # Use both Pixabay and Pexels simultaneously
    all = "all"    # Use ALL available sources (12 sources with smart fallback)


class LLMProviderConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class LLMConfig(BaseModel):
    llm_source: LLMSource = LLMSource.vscode
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    source: PromptSource = PromptSource.crosstalk
    vscode: Optional[LLMProviderConfig] = None
    openai: Optional[LLMProviderConfig] = None
    gemini: Optional[LLMProviderConfig] = None
    deepseek: Optional[LLMProviderConfig] = None


class YuanBaoConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    hy_user: str
    agent_id: str
    chat_id: str = ""
    should_remove_conversation: bool = False


class PromptConfig(BaseModel):
    prompt_writer: str = ""
    prompt_reflector: str = ""
    prompt_rewriter: str = ""


class TTSBaseConfig(BaseModel):
    api_key: str = ""
    model: str = ""
    voices: List[str] = []
    speed: float = 1.1


class TTSCosyvoiceConfig(TTSBaseConfig):
    pass


class TTSQwenConfig(TTSBaseConfig):
    pass


class TTSEdgeConfig(BaseModel):
    voices: List[str] = []
    speed: float = 1.1


class TTSKokoroConfig(BaseModel):
    voices: List[str] = ["af_bella"]
    speed: float = 1.0
    lang: str = "en-us"


class TTSConfig(BaseModel):
    source: TTSSource
    edge: Optional[TTSEdgeConfig] = None
    kokoro: Optional[TTSKokoroConfig] = None


class SubtitleConfig(BaseModel):
    font: str
    width_ratio: float = 0.8
    font_size_ratio: int = 17
    position_ratio: float = 2 / 3
    color: str = "white"
    stroke_color: str = "black"
    stroke_width: int = 1
    text_align: str = "center"
    interval: float = 0.2


class TitleConfig(SubtitleConfig):
    duration: float = 0.5


class VideoConfig(BaseModel):
    fps: int
    background_audio: str = ""
    width: int
    height: int
    title: TitleConfig
    subtitle: SubtitleConfig


class ApiConfig(BaseModel):
    database_url: str
    app_port: int
    max_concurrent_tasks: int
    task_timeout_seconds: int


class MaterialPexelsConfig(BaseModel):
    api_key: str = ""
    locale: str = ""


class MaterialPixabayConfig(BaseModel):
    api_key: str = ""
    lang: str = "zh"
    video_type: str = "all"


class MaterialUnsplashConfig(BaseModel):
    api_key: str = ""


class MaterialStabilityAIConfig(BaseModel):
    api_key: str = ""


class MaterialConfig(BaseModel):
    source: MaterialSource
    minimum_duration: int
    prompt: str
    pexels: Optional[MaterialPexelsConfig] = None
    pixabay: Optional[MaterialPixabayConfig] = None
    unsplash: Optional[MaterialUnsplashConfig] = None
    stability_ai: Optional[MaterialStabilityAIConfig] = None


class Config(BaseModel):
    llm: LLMConfig
    yuanbao: YuanBaoConfig
    prompt: Optional[PromptConfig] = None
    tts: TTSConfig
    video: VideoConfig
    api: ApiConfig
    material: MaterialConfig
