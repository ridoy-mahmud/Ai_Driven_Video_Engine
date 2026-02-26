"""
TikTok/Reels style karaoke subtitle system.

Each subtitle state is rendered as a SINGLE RGBA bitmap using Pillow,
eliminating any possibility of double/ghost subtitles from overlapping clips.

Style:
- Dark rounded pill background
- 2-4 words visible at a time
- Current word: bright white (#FFFFFF)
- Previous words: dim gray (#AAAAAA)
- Bold font with black stroke outline
- Bottom-center at ~72% from top
"""
import re
from typing import List

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, VideoClip

from schemas.config import SubtitleConfig
from utils.log import logger


# ---------------------------------------------------------------------------
# Word splitting helpers
# ---------------------------------------------------------------------------

def _split_into_words(text: str) -> List[str]:
    """Split text into words, handling English, CJK, and Bangla characters."""
    tokens = []
    current = ""
    for char in text:
        if char == " ":
            if current:
                tokens.append(current)
                current = ""
        elif re.match(
            r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af\u0980-\u09FF]',
            char,
        ):
            if current:
                tokens.append(current)
                current = ""
            tokens.append(char)
        else:
            current += char
    if current:
        tokens.append(current)
    return [t.strip() for t in tokens if t.strip()]


def _group_words_into_chunks(
    words: List[str], max_words: int = 4, max_chars: int = 30
) -> List[List[str]]:
    """Group words into small display chunks (2-4 words each).

    Each chunk is what gets displayed on screen at one time.
    """
    if not words:
        return []

    chunks: List[List[str]] = []
    current_chunk: List[str] = []
    current_chars = 0

    for word in words:
        wlen = len(word)
        if current_chunk and (
            len(current_chunk) >= max_words or current_chars + wlen + 1 > max_chars
        ):
            chunks.append(current_chunk)
            current_chunk = []
            current_chars = 0
        current_chunk.append(word)
        current_chars += wlen + 1

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


# ---------------------------------------------------------------------------
# Font loader with fallbacks
# ---------------------------------------------------------------------------

def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a PIL font with multiple fallback options."""
    candidates = [
        font_path,
        "arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default(size=size)


# ---------------------------------------------------------------------------
# Pillow-based subtitle frame renderer
# ---------------------------------------------------------------------------

def _render_subtitle_pill(
    chunk_words: List[str],
    visible_count: int,
    highlight_idx: int,
    font: ImageFont.FreeTypeFont,
    bg_opacity: int = 170,
    stroke_w: int = 2,
) -> np.ndarray:
    """Render one subtitle state as a single RGBA image.

    Parameters
    ----------
    chunk_words : all words in this chunk
    visible_count : how many words are visible (1 ... len(chunk_words))
    highlight_idx : which visible word is the "current" one (bright white).
                    Use -1 to make ALL visible words bright white.
    font : Pillow font object
    bg_opacity : alpha value for the dark background pill
    stroke_w : stroke width for text outline

    Returns
    -------
    RGBA numpy array (H, W, 4) — only the pill-sized image, NOT full-frame.
    """
    visible = chunk_words[:visible_count]
    full_text = " ".join(visible)

    # Measure text size (with stroke, since stroke adds to dimensions)
    dummy = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), full_text, font=font, stroke_width=stroke_w)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_y_offset = -bbox[1]  # compensate for top bearing

    # Pill padding
    pad_x, pad_y = 28, 14
    img_w = max(text_w + pad_x * 2, 20)
    img_h = max(text_h + pad_y * 2, 20)

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark rounded background
    draw.rounded_rectangle(
        [(0, 0), (img_w - 1, img_h - 1)],
        radius=min(12, img_h // 3),
        fill=(15, 15, 20, bg_opacity),
    )

    # Draw words one-by-one with correct colors — all in a single pass
    x_cursor = pad_x
    y_cursor = pad_y + text_y_offset

    for idx, word in enumerate(visible):
        if highlight_idx < 0 or idx == highlight_idx:
            fill_color = (255, 255, 255, 255)  # bright white
        else:
            fill_color = (170, 170, 170, 255)  # dim gray

        draw.text(
            (x_cursor, y_cursor),
            word,
            font=font,
            fill=fill_color,
            stroke_width=stroke_w,
            stroke_fill=(0, 0, 0, 220),
        )

        # Advance cursor: measure "word " (with trailing space) for all but last
        if idx < visible_count - 1:
            wbbox = d.textbbox((0, 0), word + " ", font=font, stroke_width=stroke_w)
        else:
            wbbox = d.textbbox((0, 0), word, font=font, stroke_width=stroke_w)
        x_cursor += wbbox[2] - wbbox[0]

    return np.array(img)


# ---------------------------------------------------------------------------
# Main karaoke subtitle generator
# ---------------------------------------------------------------------------

async def create_karaoke_subtitles(
    text: str,
    audio_duration: float,
    video_width: int,
    video_height: int,
    subtitle_config: SubtitleConfig,
    start_time: float = 0.0,
) -> List[VideoClip]:
    """Create TikTok/Reels style word-by-word subtitles.

    Each word state is rendered as a **single** RGBA bitmap so there is
    exactly ONE clip visible at any moment — no overlapping layers, no
    ghost/double text, no broken white fragments.

    Returns a list of ImageClips to be added to a CompositeVideoClip.
    """
    if not text or not text.strip() or audio_duration <= 0:
        return []

    subtitle_width = int(video_width * subtitle_config.width_ratio)
    font_size = int(subtitle_width / max(subtitle_config.font_size_ratio - 3, 8))
    y_position = int(video_height * 0.72)
    stroke_w = max(subtitle_config.stroke_width, 2)

    words = _split_into_words(text)
    if not words:
        return []

    font = _load_font(subtitle_config.font, font_size)

    # Determine chunk sizes based on video width
    max_chars = max(18, int(subtitle_width / (font_size * 0.52)))
    max_words_per_chunk = min(5, max(2, max_chars // 5))
    chunks = _group_words_into_chunks(
        words, max_words=max_words_per_chunk, max_chars=max_chars
    )
    if not chunks:
        return []

    # --- Distribute time across chunks proportional to character count ---
    chunk_char_counts = [max(sum(len(w) for w in c), 1) for c in chunks]
    total_chars = sum(chunk_char_counts)
    if total_chars == 0:
        return []
    chunk_durations = [(cc / total_chars) * audio_duration for cc in chunk_char_counts]

    clips: List[VideoClip] = []
    t = start_time

    for chunk_words, chunk_dur in zip(chunks, chunk_durations):
        n_words = len(chunk_words)
        if chunk_dur < 0.05 or n_words == 0:
            t += chunk_dur
            continue

        # --- Per-word timing (proportional to char count, guaranteed sum) ---
        word_chars = [max(len(w), 1) for w in chunk_words]
        wc_total = sum(word_chars)

        # Reserve 15% of chunk for the "all-bright hold" at the end
        hold_fraction = 0.15
        pop_in_dur = chunk_dur * (1.0 - hold_fraction)
        hold_dur = chunk_dur * hold_fraction

        # Per-word durations for pop-in phase (no minimum clamp — avoids overflow)
        word_durs = [(c / wc_total) * pop_in_dur for c in word_chars]

        # --- Create one ImageClip per word state (no overlaps!) ---
        word_t = t
        for wi in range(n_words):
            dur = word_durs[wi]
            if dur < 0.01:
                word_t += dur
                continue

            frame = _render_subtitle_pill(
                chunk_words,
                visible_count=wi + 1,
                highlight_idx=wi,
                font=font,
                stroke_w=stroke_w,
            )

            clip = ImageClip(frame, transparent=True)
            clip = clip.with_start(word_t).with_duration(dur)
            cx = (video_width - frame.shape[1]) // 2
            cy = y_position - frame.shape[0] // 2
            clip = clip.with_position((cx, cy))
            clips.append(clip)

            word_t += dur

        # --- "Hold" phase: all words bright white ---
        if hold_dur > 0.02:
            frame = _render_subtitle_pill(
                chunk_words,
                visible_count=n_words,
                highlight_idx=-1,  # all bright
                font=font,
                stroke_w=stroke_w,
            )
            clip = ImageClip(frame, transparent=True)
            clip = clip.with_start(word_t).with_duration(hold_dur)
            cx = (video_width - frame.shape[1]) // 2
            cy = y_position - frame.shape[0] // 2
            clip = clip.with_position((cx, cy))
            clips.append(clip)

        t += chunk_dur

    return clips


# ---------------------------------------------------------------------------
# Title subtitle (opening title card)
# ---------------------------------------------------------------------------

async def create_title_subtitle(
    text: str,
    video_width: int,
    video_height: int,
    subtitle_config: SubtitleConfig,
) -> List[VideoClip]:
    """Create an opening title with dark pill background.

    Positioned at vertical center (~42%) for maximum impact.
    Returns a list containing a single ImageClip.
    """
    if not text or not text.strip():
        return []

    subtitle_width = int(video_width * subtitle_config.width_ratio)
    font_size = int(subtitle_width / max(subtitle_config.font_size_ratio - 4, 7)) + 2
    center_y = int(video_height * 0.42)
    stroke_w = max(subtitle_config.stroke_width + 1, 3)

    font = _load_font(subtitle_config.font, font_size)

    # Wrap title to max 2 lines if too long
    display_text = text.strip()
    parts = display_text.split()
    if len(" ".join(parts)) > 30 and len(parts) > 2:
        mid = len(parts) // 2
        display_text = " ".join(parts[:mid]) + "\n" + " ".join(parts[mid:])

    # Measure text
    dummy = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), display_text, font=font, stroke_width=stroke_w)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_y_offset = -bbox[1]

    pad_x, pad_y = 36, 20
    img_w = max(text_w + pad_x * 2, 20)
    img_h = max(text_h + pad_y * 2, 20)

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark rounded background (slightly more opaque for title)
    draw.rounded_rectangle(
        [(0, 0), (img_w - 1, img_h - 1)],
        radius=min(16, img_h // 3),
        fill=(15, 15, 20, 200),
    )

    # White text with gold-tinted stroke
    draw.text(
        (pad_x, pad_y + text_y_offset),
        display_text,
        font=font,
        fill=(255, 255, 255, 255),
        stroke_width=stroke_w,
        stroke_fill=(180, 160, 60, 230),  # gold-ish stroke
        align="center",
    )

    frame = np.array(img)
    clip = ImageClip(frame, transparent=True)
    cx = (video_width - frame.shape[1]) // 2
    cy = center_y - frame.shape[0] // 2
    clip = clip.with_position((cx, cy))

    return [clip]
