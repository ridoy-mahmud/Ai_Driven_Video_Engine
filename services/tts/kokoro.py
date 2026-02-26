"""
Kokoro TTS integration using kokoro-onnx for local text-to-speech.

Install: pip install kokoro-onnx soundfile
Models are downloaded automatically on first use.
"""

import os
import asyncio
from typing import List

from .base import TextToSpeechConverter
from utils.log import logger


# Kokoro voice IDs and descriptions
KOKORO_VOICES = {
    "american_female": [
        "af_bella",        # Bella - warm, friendly
        "af_sarah",        # Sarah - clear, professional
        "af_nicole",       # Nicole - expressive
        "af_sky",          # Sky - bright, youthful
        "af_heart",        # Heart - warm, emotional
        "af_jessica",      # Jessica - confident
        "af_kore",         # Kore - unique tone
        "af_nova",         # Nova - modern
        "af_river",        # River - calm, flowing
        "af_alloy",        # Alloy - versatile
    ],
    "american_male": [
        "am_adam",         # Adam - deep, authoritative
        "am_michael",      # Michael - warm, casual
        "am_echo",         # Echo - resonant
        "am_eric",         # Eric - energetic
        "am_liam",         # Liam - youthful
        "am_onyx",         # Onyx - deep, powerful
        "am_puck",         # Puck - playful
        "am_santa",        # Santa - warm, jovial
    ],
    "british_female": [
        "bf_emma",         # Emma - elegant British
        "bf_isabella",     # Isabella - refined
        "bf_alice",        # Alice - classic
        "bf_lily",         # Lily - gentle
    ],
    "british_male": [
        "bm_george",       # George - distinguished
        "bm_lewis",        # Lewis - modern British
        "bm_daniel",       # Daniel - professional
        "bm_fable",        # Fable - storytelling
    ],
    "japanese": [
        "jf_alpha",        # Female Japanese
        "jf_gongitsune",   # Female Japanese storytelling
        "jm_kumo",         # Male Japanese
    ],
    "chinese": [
        "zf_xiaobei",      # Female Chinese
        "zf_xiaoni",       # Female Chinese warm
        "zf_xiaoxuan",     # Female Chinese expressive
        "zm_yunjian",      # Male Chinese
        "zm_yunxi",        # Male Chinese calm
    ],
    "french": [
        "ff_siwis",        # Female French
    ],
    "hindi": [
        "hf_alpha",        # Female Hindi
        "hm_omega",        # Male Hindi
    ],
    "italian": [
        "if_sara",         # Female Italian
        "im_nicola",       # Male Italian
    ],
    "portuguese": [
        "pf_camila",       # Female Portuguese (Brazil)
        "pm_alex",         # Male Portuguese (Brazil)
    ],
    "spanish": [
        "ef_dora",         # Female Spanish
        "em_alex",         # Male Spanish
    ],
}

# Flat list of all Kokoro voices for easy lookup
ALL_KOKORO_VOICES = []
for _group, _voices in KOKORO_VOICES.items():
    ALL_KOKORO_VOICES.extend(_voices)

# Language code mapping for Kokoro
KOKORO_LANG_MAP = {
    "american_female": "en-us",
    "american_male": "en-us",
    "british_female": "en-gb",
    "british_male": "en-gb",
    "japanese": "ja",
    "chinese": "zh",
    "french": "fr-fr",
    "hindi": "hi",
    "italian": "it",
    "portuguese": "pt-br",
    "spanish": "es",
}


def _get_kokoro_lang(voice: str) -> str:
    """Get the language code for a Kokoro voice."""
    for group, voices in KOKORO_VOICES.items():
        if voice in voices:
            return KOKORO_LANG_MAP.get(group, "en-us")
    return "en-us"


class KokoroTextToSpeechConverter(TextToSpeechConverter):
    """Local Kokoro TTS converter using kokoro-onnx.
    
    Requires: pip install kokoro-onnx soundfile
    Models are downloaded automatically on first use (~80MB).
    """

    def __init__(self, voices: List[str], folder: str, speed: float = 1.0, lang: str = "en-us"):
        super().__init__(voices, folder, speed)
        self.lang = lang
        self._kokoro = None

    async def _get_kokoro(self):
        """Lazy-initialize Kokoro TTS engine."""
        if self._kokoro is None:
            try:
                from kokoro_onnx import Kokoro
                self._kokoro = Kokoro(
                    "kokoro-v0_19.onnx",
                    "voices.bin"
                )
                logger.info("Kokoro TTS engine initialized successfully")
            except ImportError:
                raise ImportError(
                    "kokoro-onnx is not installed. Install it with: pip install kokoro-onnx soundfile"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Kokoro TTS: {e}")
                raise
        return self._kokoro

    async def generate_audio(self, content: str, voice: str, file_name: str, speech_rate: float = 1.0):
        """Generate audio using Kokoro TTS."""
        kokoro = await self._get_kokoro()

        lang = _get_kokoro_lang(voice)

        # Run synthesis in thread pool since it's CPU-bound
        loop = asyncio.get_event_loop()
        samples, sample_rate = await loop.run_in_executor(
            None,
            lambda: kokoro.create(content, voice=voice, speed=self.speed, lang=lang)
        )

        # Save as WAV first, then convert to MP3 format
        import soundfile as sf
        wav_file = file_name.replace(".mp3", ".wav")
        sf.write(wav_file, samples, sample_rate)

        # Convert WAV to MP3 using ffmpeg
        import subprocess
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", wav_file, "-codec:a", "libmp3lame", "-qscale:a", "2", file_name],
                check=True,
                capture_output=True,
            )
            # Clean up WAV file
            if os.path.exists(wav_file):
                os.remove(wav_file)
        except subprocess.CalledProcessError:
            # If ffmpeg fails, rename WAV to MP3 path (moviepy can handle WAV)
            import shutil
            shutil.move(wav_file, file_name)

        logger.info(f"Kokoro TTS generated: {file_name} (voice={voice}, lang={lang})")
