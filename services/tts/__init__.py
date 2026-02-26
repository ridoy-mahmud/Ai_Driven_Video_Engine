from .cosyvoice import CosyvoiceTextToSpeechConverter
from .qwen import QwenTextToSpeechConverter
from .edge import EdgeTextToSpeechConverter

__all__ = [
    "CosyvoiceTextToSpeechConverter", 
    "QwenTextToSpeechConverter",
    "EdgeTextToSpeechConverter",
]


def get_kokoro_converter():
    """Lazy import for KokoroTextToSpeechConverter to avoid requiring soundfile/kokoro-onnx."""
    from .kokoro import KokoroTextToSpeechConverter
    return KokoroTextToSpeechConverter
