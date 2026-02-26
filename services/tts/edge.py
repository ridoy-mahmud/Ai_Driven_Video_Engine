import asyncio
import re
from typing import List

import edge_tts

from .base import TextToSpeechConverter

# Language detection patterns and their default voices
LANGUAGE_VOICE_MAP = {
    "zh": ("zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"),
    "ja": ("ja-JP-NanamiNeural", "ja-JP-KeitaNeural"),
    "ko": ("ko-KR-SunHiNeural", "ko-KR-InJoonNeural"),
    "en": ("en-US-JennyNeural", "en-US-GuyNeural"),
    "es": ("es-ES-ElviraNeural", "es-ES-AlvaroNeural"),
    "fr": ("fr-FR-DeniseNeural", "fr-FR-HenriNeural"),
    "de": ("de-DE-KatjaNeural", "de-DE-ConradNeural"),
    "pt": ("pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"),
    "it": ("it-IT-ElsaNeural", "it-IT-DiegoNeural"),
    "hi": ("hi-IN-SwaraNeural", "hi-IN-MadhurNeural"),
    "ar": ("ar-SA-ZariyahNeural", "ar-SA-HamedNeural"),
    "ru": ("ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"),
    "tr": ("tr-TR-EmelNeural", "tr-TR-AhmetNeural"),
    "nl": ("nl-NL-ColetteNeural", "nl-NL-MaartenNeural"),
    "bn": ("bn-BD-NabanitaNeural", "bn-BD-PradeepNeural"),
}


def _detect_language(text: str) -> str:
    """Simple language detection based on character ranges."""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    japanese_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
    korean_chars = len(re.findall(r'[\uac00-\ud7af]', text))
    bengali_chars = len(re.findall(r'[\u0980-\u09FF]', text))
    total = len(text)
    if total == 0:
        return "en"
    if chinese_chars / total > 0.1:
        return "zh"
    if japanese_chars / total > 0.05:
        return "ja"
    if korean_chars / total > 0.1:
        return "ko"
    if bengali_chars / total > 0.1:
        return "bn"
    return "en"


class EdgeTextToSpeechConverter(TextToSpeechConverter):
    """Free Microsoft Edge TTS converter using edge-tts library."""

    def __init__(self, voices: List[str], folder: str, speed: float = 1.1):
        super().__init__(voices, folder, speed)

    def _get_compatible_voice(self, voice: str, content: str) -> str:
        """Ensure the voice is compatible with the content language.
        If an English voice is used with Chinese text (or vice versa), swap to a matching voice."""
        lang = _detect_language(content)
        voice_lang = voice.split("-")[0].lower() if "-" in voice else "en"
        
        # If voice language matches content language, use as-is
        if voice_lang == lang:
            return voice
        
        # Otherwise, pick a default voice for the detected language
        defaults = LANGUAGE_VOICE_MAP.get(lang, LANGUAGE_VOICE_MAP["en"])
        return defaults[0]

    async def generate_audio(self, content: str, voice: str, file_name: str):
        """Generate audio using Microsoft Edge TTS."""
        rate_percentage = f"{int((self.speed - 1) * 100):+d}%"
        compatible_voice = self._get_compatible_voice(voice, content)
        communicate = edge_tts.Communicate(content, compatible_voice, rate=rate_percentage)
        await communicate.save(file_name)


# Popular Edge TTS voices for different languages
EDGE_VOICES = {
    "english": [
        "en-US-JennyNeural",              # Female, friendly
        "en-US-GuyNeural",                # Male, casual
        "en-US-AriaNeural",               # Female, cheerful
        "en-US-DavisNeural",              # Male, confident
        "en-US-AmberNeural",              # Female, warm
        "en-US-BrandonNeural",            # Male, energetic
        "en-US-EricNeural",               # Male, professional
        "en-US-ChristopherNeural",        # Male, clear
        "en-US-AvaNeural",                # Female, expressive
        "en-US-AvaMultilingualNeural",    # Female, multilingual
        "en-US-AndrewNeural",             # Male, warm
        "en-US-AndrewMultilingualNeural", # Male, multilingual
        "en-US-EmmaNeural",               # Female, bright
        "en-US-EmmaMultilingualNeural",   # Female, multilingual
        "en-US-BrianNeural",              # Male, narrative
        "en-US-BrianMultilingualNeural",  # Male, multilingual
        "en-US-MichelleNeural",           # Female, professional
        "en-US-RogerNeural",              # Male, mature
        "en-US-SteffanNeural",            # Male, articulate
        "en-US-CoraNeural",               # Female, mature
        "en-US-JasonNeural",              # Male, standard
        "en-US-MonicaNeural",             # Female, gentle
        "en-US-SaraNeural",               # Female, sweet
        "en-US-TonyNeural",               # Male, youthful
        "en-US-NancyNeural",              # Female, clear
        "en-US-AshleyNeural",             # Female, casual
        "en-US-ElizabethNeural",          # Female, elegant
        "en-US-JacobNeural",              # Male, friendly
        "en-GB-SoniaNeural",              # Female, British
        "en-GB-RyanNeural",               # Male, British
        "en-GB-LibbyNeural",              # Female, British youthful
        "en-GB-MaisieNeural",             # Female, British warm
        "en-GB-ThomasNeural",             # Male, British formal
        "en-AU-NatashaNeural",            # Female, Australian
        "en-AU-WilliamNeural",            # Male, Australian
        "en-IN-NeerjaNeural",             # Female, Indian English
        "en-IN-PrabhatNeural",            # Male, Indian English
        "en-CA-ClaraNeural",              # Female, Canadian
        "en-CA-LiamNeural",              # Male, Canadian
    ],
    "chinese": [
        "zh-CN-XiaoxiaoNeural",   # Female, gentle
        "zh-CN-YunxiNeural",      # Male, calm
        "zh-CN-XiaoyiNeural",     # Female, sweet
        "zh-CN-YunjianNeural",    # Male, energetic
        "zh-CN-XiaohanNeural",    # Female, warm
        "zh-CN-XiaomengNeural",   # Female, cute
        "zh-CN-XiaochenNeural",   # Female, cheerful
        "zh-CN-XiaoruiNeural",    # Female, senior
        "zh-CN-XiaoshuangNeural", # Female, child
        "zh-CN-XiaoxuanNeural",   # Female, dramatic
        "zh-CN-XiaoyanNeural",    # Female, calm
        "zh-CN-XiaozhenNeural",   # Female, warm
        "zh-CN-YunfengNeural",    # Male, dramatic
        "zh-CN-YunhaoNeural",     # Male, warm
        "zh-CN-YunyeNeural",      # Male, narrative
        "zh-CN-YunyangNeural",    # Male, newscast
        "zh-TW-HsiaoChenNeural",  # Female, Taiwanese
        "zh-TW-YunJheNeural",     # Male, Taiwanese
        "zh-TW-HsiaoYuNeural",    # Female, Taiwanese warm
    ],
    "japanese": [
        "ja-JP-NanamiNeural",     # Female, polite
        "ja-JP-KeitaNeural",      # Male, calm
        "ja-JP-AoiNeural",        # Female, cheerful
        "ja-JP-DaichiNeural",     # Male, friendly
        "ja-JP-MayuNeural",       # Female, sweet
        "ja-JP-ShioriNeural",     # Female, professional
    ],
    "spanish": [
        "es-ES-ElviraNeural",     # Female, Spanish
        "es-ES-AlvaroNeural",     # Male, Spanish
        "es-MX-DaliaNeural",      # Female, Mexican
        "es-MX-JorgeNeural",      # Male, Mexican
        "es-AR-ElenaNeural",      # Female, Argentine
        "es-AR-TomasNeural",      # Male, Argentine
        "es-CO-SalomeNeural",     # Female, Colombian
        "es-CO-GonzaloNeural",    # Male, Colombian
    ],
    "french": [
        "fr-FR-DeniseNeural",     # Female, French
        "fr-FR-HenriNeural",      # Male, French
        "fr-FR-VivienneMultilingualNeural",  # Female, multilingual
        "fr-CA-SylvieNeural",     # Female, Canadian French
        "fr-CA-JeanNeural",       # Male, Canadian French
    ],
    "german": [
        "de-DE-KatjaNeural",      # Female, German
        "de-DE-ConradNeural",     # Male, German
        "de-DE-AmalaNeural",      # Female, German warm
        "de-DE-FlorianMultilingualNeural",   # Male, multilingual
        "de-AT-IngridNeural",     # Female, Austrian
        "de-AT-JonasNeural",      # Male, Austrian
    ],
    "korean": [
        "ko-KR-SunHiNeural",     # Female, Korean
        "ko-KR-InJoonNeural",    # Male, Korean
        "ko-KR-BongJinNeural",   # Male, Korean mature
        "ko-KR-YuJinNeural",     # Female, Korean warm
    ],
    "portuguese": [
        "pt-BR-FranciscaNeural",  # Female, Brazilian
        "pt-BR-AntonioNeural",    # Male, Brazilian
        "pt-PT-RaquelNeural",     # Female, Portuguese
        "pt-PT-DuarteNeural",     # Male, Portuguese
    ],
    "italian": [
        "it-IT-ElsaNeural",      # Female, Italian
        "it-IT-DiegoNeural",     # Male, Italian
        "it-IT-IsabellaNeural",  # Female, Italian warm
        "it-IT-GiuseppeNeural",  # Male, Italian mature
    ],
    "hindi": [
        "hi-IN-SwaraNeural",     # Female, Hindi
        "hi-IN-MadhurNeural",    # Male, Hindi
    ],
    "arabic": [
        "ar-SA-ZariyahNeural",   # Female, Arabic
        "ar-SA-HamedNeural",     # Male, Arabic
        "ar-EG-SalmaNeural",     # Female, Egyptian Arabic
        "ar-EG-ShakirNeural",    # Male, Egyptian Arabic
    ],
    "russian": [
        "ru-RU-SvetlanaNeural",  # Female, Russian
        "ru-RU-DmitryNeural",    # Male, Russian
    ],
    "turkish": [
        "tr-TR-EmelNeural",      # Female, Turkish
        "tr-TR-AhmetNeural",     # Male, Turkish
    ],
    "dutch": [
        "nl-NL-ColetteNeural",   # Female, Dutch
        "nl-NL-MaartenNeural",   # Male, Dutch
    ],
    "bangla": [
        "bn-BD-NabanitaNeural",  # Female, Bangla
        "bn-BD-PradeepNeural",   # Male, Bangla
        "bn-IN-BashkarNeural",   # Male, Bengali (India)
        "bn-IN-TanishaaNeural",  # Female, Bengali (India)
    ]
}