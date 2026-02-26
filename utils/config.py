import sys
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import toml as _toml_fallback

from schemas.config import Config, PromptConfig, PromptSource


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
