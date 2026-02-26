import os
import random
import subprocess
from typing import Any, Dict, List, Optional

import numpy as np
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    VideoClip,
    VideoFileClip,
    vfx,
)

from schemas.config import VideoConfig
from schemas.video import MaterialInfo, VideoTranscript
from utils.log import logger
from utils.subtitle_advanced import create_karaoke_subtitles, create_title_subtitle


def create_filelist(input_files: List[str], list_file: str):
    with open(list_file, "w") as f:
        for file in input_files:
            f.write(f"file '{file}'\n")


async def merge_videos(
    input_files: List[str],
    output_file: str,
    list_file: str,
    background_audio: str = "",
):
    create_filelist(input_files, list_file)

    # If no background audio or file doesn't exist, merge without music
    if not background_audio or not os.path.exists(background_audio):
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            output_file,
        ]
    else:
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-stream_loop",
            "-1",
            "-i",
            background_audio,
            "-filter_complex",
            "[1:a]volume=0.1[v1];[0:a][v1]amerge=inputs=2[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            output_file,
        ]

    try:
        subprocess.run(command, check=True)
        logger.info("Video created successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"FFMPEG error: {e}")
    except Exception as e:
        logger.error(f"Error creating video: {e}")


def transition_video(video: VideoClip, is_reels: bool = False) -> VideoClip:
    """Apply transition effects to video clips.
    
    For reels, transitions are faster and more dynamic.
    """
    shuffle_side = random.choice(["left", "right", "top", "bottom"])
    fade_dur = 0.3 if is_reels else 0.5
    transition_funcs = [
        lambda c: c.with_effects([vfx.CrossFadeIn(fade_dur)]),
        lambda c: c.with_effects([vfx.SlideIn(fade_dur, shuffle_side)]),
        lambda c: c,
    ]
    if is_reels:
        probabilities = [0.45, 0.45, 0.1]  # More transitions for reels
    else:
        probabilities = [0.4, 0.4, 0.2]
    shuffle_transition = random.choices(transition_funcs, probabilities, k=1)[0]
    return shuffle_transition(video)


def apply_zoom_in(video: VideoClip, zoom_factor: float = 1.15, duration: float = None) -> VideoClip:
    """Apply a smooth zoom-in (Ken Burns) effect to a video clip.
    
    The clip gradually zooms from 1.0x to zoom_factor over its duration.
    """
    if duration is None:
        duration = video.duration
    
    w, h = video.size
    
    def zoom_effect(get_frame, t):
        """Apply progressive zoom at time t."""
        progress = min(t / duration, 1.0)
        current_zoom = 1.0 + (zoom_factor - 1.0) * progress
        
        frame = get_frame(t)
        new_h, new_w = frame.shape[:2]
        
        # Calculate crop region for zoom
        crop_w = int(new_w / current_zoom)
        crop_h = int(new_h / current_zoom)
        x_offset = (new_w - crop_w) // 2
        y_offset = (new_h - crop_h) // 2
        
        cropped = frame[y_offset:y_offset + crop_h, x_offset:x_offset + crop_w]
        
        # Resize back to original dimensions
        from PIL import Image
        img = Image.fromarray(cropped)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        return np.array(img)
    
    return video.transform(zoom_effect)


def apply_zoom_out(video: VideoClip, zoom_factor: float = 1.15) -> VideoClip:
    """Apply a smooth zoom-out effect (starts zoomed in, ends at 1.0x)."""
    duration = video.duration
    w, h = video.size
    
    def zoom_effect(get_frame, t):
        progress = min(t / duration, 1.0)
        current_zoom = zoom_factor - (zoom_factor - 1.0) * progress
        
        frame = get_frame(t)
        new_h, new_w = frame.shape[:2]
        
        crop_w = int(new_w / current_zoom)
        crop_h = int(new_h / current_zoom)
        x_offset = (new_w - crop_w) // 2
        y_offset = (new_h - crop_h) // 2
        
        cropped = frame[y_offset:y_offset + crop_h, x_offset:x_offset + crop_w]
        
        from PIL import Image
        img = Image.fromarray(cropped)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        return np.array(img)
    
    return video.transform(zoom_effect)


def apply_pan_effect(video: VideoClip, direction: str = "left") -> VideoClip:
    """Apply a slow pan effect across the video frame."""
    duration = video.duration
    
    def pan_effect(get_frame, t):
        progress = min(t / duration, 1.0)
        frame = get_frame(t)
        h, w = frame.shape[:2]
        
        # Pan amount: 10% of frame width/height
        pan_amount = int(w * 0.1)
        
        if direction == "left":
            offset = int(pan_amount * progress)
            # Shift left: crop from offset
            cropped = frame[:, offset:w]
            # Pad right side
            pad = frame[:, :offset]
            return np.concatenate([cropped, pad], axis=1)
        elif direction == "right":
            offset = int(pan_amount * (1.0 - progress))
            cropped = frame[:, offset:w]
            pad = frame[:, :offset]
            return np.concatenate([cropped, pad], axis=1)
        return frame
    
    return video.transform(pan_effect)


def apply_speed_effect(video: VideoClip, speed_factor: float) -> VideoClip:
    """Apply speed multiplier to a video clip."""
    if speed_factor == 1.0:
        return video
    return video.with_effects([vfx.MultiplySpeed(speed_factor)])


def apply_random_effect(video: VideoClip, is_reels: bool = False) -> VideoClip:
    """Apply a random cinematic effect to make videos more engaging.
    
    For reels, effects are more aggressive and frequent.
    """
    effects = [
        lambda v: apply_zoom_in(v, zoom_factor=random.uniform(1.08, 1.2)),
        lambda v: apply_zoom_out(v, zoom_factor=random.uniform(1.08, 1.2)),
        lambda v: apply_ken_burns(v),
        lambda v: apply_zoom_pulse(v),
        lambda v: v,  # No effect
    ]
    
    if is_reels:
        # Reels: always apply an effect
        probabilities = [0.3, 0.2, 0.25, 0.15, 0.1]
    else:
        # Regular: sometimes no effect
        probabilities = [0.25, 0.2, 0.15, 0.1, 0.3]
    
    chosen_effect = random.choices(effects, probabilities, k=1)[0]
    return chosen_effect(video)


# ─────────────────────────────────────────────────────────────────────────────
# Advanced animation effects
# ─────────────────────────────────────────────────────────────────────────────

def apply_ken_burns(video: VideoClip, zoom_start: float = 1.0, zoom_end: float = 1.2) -> VideoClip:
    """Ken Burns effect: combined zoom + pan, like documentary-style cinema.
    
    Randomly chooses a start corner and zooms/pans to the opposite corner.
    """
    duration = video.duration
    # Random pan direction
    directions = ["top_left_to_bottom_right", "bottom_right_to_top_left",
                  "top_right_to_bottom_left", "bottom_left_to_top_right"]
    direction = random.choice(directions)

    def kb_effect(get_frame, t):
        progress = min(t / max(duration, 0.01), 1.0)
        current_zoom = zoom_start + (zoom_end - zoom_start) * progress
        
        frame = get_frame(t)
        h, w = frame.shape[:2]
        
        crop_w = int(w / current_zoom)
        crop_h = int(h / current_zoom)
        
        # Pan offset based on direction
        max_x = w - crop_w
        max_y = h - crop_h
        
        if direction == "top_left_to_bottom_right":
            x_off = int(max_x * progress)
            y_off = int(max_y * progress)
        elif direction == "bottom_right_to_top_left":
            x_off = int(max_x * (1 - progress))
            y_off = int(max_y * (1 - progress))
        elif direction == "top_right_to_bottom_left":
            x_off = int(max_x * (1 - progress))
            y_off = int(max_y * progress)
        else:  # bottom_left_to_top_right
            x_off = int(max_x * progress)
            y_off = int(max_y * (1 - progress))
        
        x_off = max(0, min(x_off, max_x))
        y_off = max(0, min(y_off, max_y))
        
        cropped = frame[y_off:y_off + crop_h, x_off:x_off + crop_w]
        
        from PIL import Image
        img = Image.fromarray(cropped)
        img = img.resize((w, h), Image.LANCZOS)
        return np.array(img)
    
    return video.transform(kb_effect)


def apply_zoom_pulse(video: VideoClip, max_zoom: float = 1.12, pulses: int = 2) -> VideoClip:
    """Zoom pulse: rhythmic zoom in/out, like a heartbeat or music beat.
    
    Creates a pulsing zoom effect that zooms in and out cyclically.
    """
    duration = video.duration
    import math

    def pulse_effect(get_frame, t):
        progress = t / max(duration, 0.01)
        # Sine wave for smooth pulse
        pulse = abs(math.sin(progress * math.pi * pulses))
        current_zoom = 1.0 + (max_zoom - 1.0) * pulse
        
        frame = get_frame(t)
        h, w = frame.shape[:2]
        
        crop_w = int(w / current_zoom)
        crop_h = int(h / current_zoom)
        x_off = (w - crop_w) // 2
        y_off = (h - crop_h) // 2
        
        cropped = frame[y_off:y_off + crop_h, x_off:x_off + crop_w]
        
        from PIL import Image
        img = Image.fromarray(cropped)
        img = img.resize((w, h), Image.LANCZOS)
        return np.array(img)
    
    return video.transform(pulse_effect)


def apply_shake(video: VideoClip, intensity: float = 5.0) -> VideoClip:
    """Camera shake effect: adds subtle random shake for energy/urgency.
    
    Good for dramatic moments, news flashes, or high-energy reels.
    """
    def shake_effect(get_frame, t):
        frame = get_frame(t)
        h, w = frame.shape[:2]
        
        # Pseudo-random shake based on time (deterministic for same t)
        seed = int(t * 100)
        rng = random.Random(seed)
        dx = rng.randint(int(-intensity), int(intensity))
        dy = rng.randint(int(-intensity), int(intensity))
        
        # Shift frame
        result = np.zeros_like(frame)
        src_x1 = max(0, -dx)
        src_y1 = max(0, -dy)
        src_x2 = min(w, w - dx)
        src_y2 = min(h, h - dy)
        dst_x1 = max(0, dx)
        dst_y1 = max(0, dy)
        dst_x2 = min(w, w + dx)
        dst_y2 = min(h, h + dy)
        
        sh = min(src_y2 - src_y1, dst_y2 - dst_y1)
        sw = min(src_x2 - src_x1, dst_x2 - dst_x1)
        if sh > 0 and sw > 0:
            result[dst_y1:dst_y1 + sh, dst_x1:dst_x1 + sw] = frame[src_y1:src_y1 + sh, src_x1:src_x1 + sw]
        
        return result
    
    return video.transform(shake_effect)


def apply_brightness_flash(video: VideoClip, flash_at: float = 0.0) -> VideoClip:
    """Brightness flash: brief white flash at a specific time, like a camera flash.
    
    Great for transitions or emphasis moments.
    """
    def flash_effect(get_frame, t):
        frame = get_frame(t)
        # Flash fades in 0.1s and out in 0.2s
        dt = abs(t - flash_at)
        if dt < 0.3:
            bright = 1.0 + (1.0 - dt / 0.3) * 1.5  # Up to 2.5x brightness
            frame = np.clip(frame * bright, 0, 255).astype(np.uint8)
        return frame
    
    return video.transform(flash_effect)


def apply_vignette(video: VideoClip, strength: float = 0.5) -> VideoClip:
    """Vignette effect: darkened corners for a cinematic look.
    
    Creates a subtle circular gradient that darkens the edges.
    """
    _vignette_mask = None

    def vignette_effect(get_frame, t):
        nonlocal _vignette_mask
        frame = get_frame(t)
        h, w = frame.shape[:2]
        
        if _vignette_mask is None:
            # Create vignette mask once
            y = np.linspace(-1, 1, h)
            x = np.linspace(-1, 1, w)
            X, Y = np.meshgrid(x, y)
            dist = np.sqrt(X**2 + Y**2)
            _vignette_mask = np.clip(1.0 - (dist - 0.7) * strength * 2, 0.3, 1.0)
            _vignette_mask = np.stack([_vignette_mask] * 3, axis=-1)
        
        return np.clip(frame * _vignette_mask, 0, 255).astype(np.uint8)
    
    return video.transform(vignette_effect)


def apply_color_shift(video: VideoClip, hue_shift: float = 0.1) -> VideoClip:
    """Subtle color temperature shift over time for visual interest.
    
    Gradually shifts warm/cool color tone.
    """
    def color_effect(get_frame, t):
        frame = get_frame(t).copy()
        h, w = frame.shape[:2]
        progress = t / max(video.duration, 0.01)
        
        # Warm → Cool shift
        warm = 1.0 + hue_shift * (1 - progress)
        cool = 1.0 + hue_shift * progress
        
        frame[:, :, 0] = np.clip(frame[:, :, 0] * cool, 0, 255)  # Blue channel
        frame[:, :, 2] = np.clip(frame[:, :, 2] * warm, 0, 255)  # Red channel
        
        return frame.astype(np.uint8)
    
    return video.transform(color_effect)


def apply_rotation(video: VideoClip, max_angle: float = 3.0) -> VideoClip:
    """Gentle rotation effect for dynamic feel.
    
    Slowly rotates the frame slightly left then right.
    """
    import math

    def rotation_effect(get_frame, t):
        frame = get_frame(t)
        progress = t / max(video.duration, 0.01)
        angle = max_angle * math.sin(progress * math.pi * 2)
        
        from PIL import Image
        img = Image.fromarray(frame)
        rotated = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(0, 0, 0))
        return np.array(rotated)
    
    return video.transform(rotation_effect)


def _apply_effect_by_name(video: VideoClip, effect_name: str) -> VideoClip:
    """Apply a named effect to a video clip. Used by reels multi-clip renderer."""
    try:
        if effect_name == "zoom_in":
            return apply_zoom_in(video, zoom_factor=random.uniform(1.08, 1.18))
        elif effect_name == "zoom_out":
            return apply_zoom_out(video, zoom_factor=random.uniform(1.08, 1.18))
        elif effect_name == "pan_left":
            return apply_pan_effect(video, direction="left")
        elif effect_name == "pan_right":
            return apply_pan_effect(video, direction="right")
        elif effect_name == "ken_burns":
            return apply_ken_burns(video)
        elif effect_name == "zoom_pulse":
            return apply_zoom_pulse(video)
        elif effect_name == "shake":
            return apply_shake(video, intensity=3.0)
        elif effect_name == "vignette":
            return apply_vignette(video)
        elif effect_name == "color_shift":
            return apply_color_shift(video)
        elif effect_name == "rotation":
            return apply_rotation(video, max_angle=2.0)
        elif effect_name == "flash":
            return apply_brightness_flash(video, flash_at=0.0)
        elif effect_name == "none":
            return video
        else:
            return video
    except Exception as e:
        logger.warning(f"Effect '{effect_name}' failed: {e}")
        return video


def resize_video(video: VideoFileClip, video_width: int, video_height: int) -> VideoClip:
    if video.size[0] / video.size[1] != video_width / video_height:
        target_aspect_ratio = video_width / video_height
        video_aspect_ratio = video.size[0] / video.size[1]

        if video_aspect_ratio > target_aspect_ratio:
            new_width = int(video.size[1] * target_aspect_ratio)
            crop_x = (video.size[0] - new_width) // 2
            video = video.cropped(x1=crop_x, x2=crop_x + new_width, y1=0, y2=video.size[1])
        else:
            new_height = int(video.size[0] / target_aspect_ratio)
            crop_y = (video.size[1] - new_height) // 2
            video = video.cropped(x1=0, x2=video.size[0], y1=crop_y, y2=crop_y + new_height)

    if video.size[0] != video_width:
        video = video.resized((video_width, video_height))
    return video


def formatter_text(text: str) -> str:
    text = text.replace("‘", "“").replace("’", "”").strip()
    return text


async def create_video(
    videos: List[MaterialInfo],
    video_transcript: VideoTranscript,
    folder: str,
    output_file: str,
    video_config: VideoConfig,
    video_type: str = "short_content",
    video_speed: float = 1.0,
    effect_plan: Optional[List[Dict[str, Any]]] = None,
) -> VideoClip:
    logger.info(f"Creating video... (type={video_type}, speed={video_speed}x)")

    is_reels = (video_type == "reels")
    
    title = video_transcript.title
    video_files = []
    video_idx = 0  # Track which material clip to use
    
    for i, paragraph in enumerate(video_transcript.paragraphs, start=1):
        logger.info(f"Processing paragraph {i}/{len(video_transcript.paragraphs)}")

        base_name = f"{i}.mp4"
        video_file = os.path.join(folder, base_name)
        video_files.append(base_name)

        # Determine how many material clips this paragraph should consume
        para_effect = None
        if effect_plan and (i - 1) < len(effect_plan):
            para_effect = effect_plan[i - 1]
        
        num_clips_for_para = 1
        if is_reels and para_effect:
            num_clips_for_para = max(2, para_effect.get("num_clips", 2))

        if os.path.exists(video_file):
            video_idx += num_clips_for_para
            continue
        
        # Load material clip(s) for this paragraph
        para_video_clips = []
        for _ in range(num_clips_for_para):
            if video_idx < len(videos):
                v = VideoFileClip(videos[video_idx].video_path).without_audio()
                v = resize_video(v, video_config.width, video_config.height)
                para_video_clips.append(v)
            elif videos:
                # Reuse last available clip
                v = VideoFileClip(videos[-1].video_path).without_audio()
                v = resize_video(v, video_config.width, video_config.height)
                para_video_clips.append(v)
            video_idx += 1

        # If somehow no clips loaded, use the last available
        if not para_video_clips and videos:
            v = VideoFileClip(videos[-1].video_path).without_audio()
            v = resize_video(v, video_config.width, video_config.height)
            para_video_clips.append(v)

        text_clips = []
        audio_clips = []
        duration_start = 0

        dialogues = paragraph.dialogues
        for j, dialogue in enumerate(dialogues, start=1):
            logger.info(f"Processing dialogue {j}/{len(dialogues)}")

            texts = dialogue.contents

            for k, text in enumerate(texts, start=1):
                if i == 1 and j == 1 and k == 1:
                    duration_delta = video_config.title.duration
                    title = formatter_text(title)
                    # Use advanced title subtitle with dark bg pill at center
                    title_clips = await create_title_subtitle(
                        title, video_config.width, video_config.height, video_config.title
                    )
                    for tc in title_clips:
                        tc = tc.with_duration(duration_delta).with_start(duration_start)
                        text_clips.append(tc)
                else:
                    duration_delta = video_config.subtitle.interval

                audio_file = os.path.join(folder, f"{i}_{j}_{k}.mp3")
                audio = AudioFileClip(audio_file)

                text = formatter_text(text)
                
                # Use karaoke word-by-word highlighted subtitles at TOP
                karaoke_clips = await create_karaoke_subtitles(
                    text,
                    audio.duration,
                    video_config.width,
                    video_config.height,
                    video_config.subtitle,
                    start_time=duration_start + duration_delta,
                )
                text_clips.extend(karaoke_clips)

                audio_clip = audio.with_start(duration_start + duration_delta)
                audio_clips.append(audio_clip)

                duration_start += duration_delta + audio.duration

        total_para_duration = duration_start

        # --- Build video background ---
        if is_reels and len(para_video_clips) > 1:
            # REELS MULTI-CLIP: Quick-cut between multiple B-roll clips
            clip_dur = total_para_duration / len(para_video_clips)
            bg_clips = []
            effect_names = ["zoom_in", "zoom_out", "pan_left", "pan_right",
                            "ken_burns", "zoom_pulse", "shake"]
            
            for cidx, vc in enumerate(para_video_clips):
                start_t = cidx * clip_dur
                vc = vc.with_duration(clip_dur).with_start(start_t)
                
                # Apply a different cinematic effect to each sub-clip
                eff = effect_names[cidx % len(effect_names)]
                vc = _apply_effect_by_name(vc, eff)
                
                # Fast transition between sub-clips (except first)
                if cidx > 0:
                    try:
                        vc = vc.with_effects([vfx.CrossFadeIn(0.15)])
                    except Exception:
                        pass
                
                bg_clips.append(vc)
            
            logger.info(f"Reels paragraph {i}: {len(bg_clips)} quick-cut clips, {clip_dur:.1f}s each")
            final_video = CompositeVideoClip(bg_clips + text_clips)
        else:
            # Standard: single clip background
            video = para_video_clips[0] if para_video_clips else para_video_clips[0]
            
            # Apply transition based on LLM effect plan
            if i > 1:
                video = _apply_planned_transition(video, para_effect, is_reels)
            
            # Apply LLM-chosen cinematic effect (zoom/pan)
            video = _apply_planned_effect(video, para_effect, is_reels)
            
            final_video = CompositeVideoClip([video] + text_clips)

        final_audio = CompositeAudioClip(audio_clips)
        final_video = final_video.with_audio(final_audio).with_duration(final_audio.duration)

        # Apply speed effect (for reels, default 1.3x; user can override)
        if video_speed != 1.0:
            final_video = apply_speed_effect(final_video, video_speed)

        try:
            final_video.write_videofile(
                video_file, codec="libx264", fps=video_config.fps, temp_audiofile_path=folder, threads=4
            )
        except Exception as e:
            logger.error(f"Error writing video file: {e}")
            if os.path.exists(video_file):
                os.remove(video_file)
            raise e

    logger.info("Merging videos...")
    list_file = os.path.join(folder, "listfile.txt")
    await merge_videos(video_files, output_file, list_file, video_config.background_audio)

    return None


def _apply_planned_transition(video: VideoClip, para_effect: Optional[Dict], is_reels: bool) -> VideoClip:
    """Apply transition based on LLM effect plan, with fallback to random."""
    if not para_effect:
        return transition_video(video, is_reels)
    
    transition = para_effect.get("transition", "crossfade")
    intensity = para_effect.get("intensity", 0.5)
    fade_dur = 0.2 + (0.5 * (1.0 - intensity))  # Higher intensity = faster transition
    
    try:
        if transition == "crossfade":
            return video.with_effects([vfx.CrossFadeIn(fade_dur)])
        elif transition in ("slide_left", "slide_right", "slide_up"):
            direction = transition.replace("slide_", "")
            return video.with_effects([vfx.SlideIn(fade_dur, direction)])
        elif transition == "none":
            return video
        else:
            return transition_video(video, is_reels)
    except Exception as e:
        logger.warning(f"Transition '{transition}' failed: {e}, using fallback")
        return transition_video(video, is_reels)


def _apply_planned_effect(video: VideoClip, para_effect: Optional[Dict], is_reels: bool) -> VideoClip:
    """Apply cinematic effect based on LLM plan, with fallback to random."""
    if not para_effect:
        return apply_random_effect(video, is_reels)
    
    effect = para_effect.get("effect", "none")
    intensity = para_effect.get("intensity", 0.5)
    
    # Map intensity (0.1-1.0) to zoom factor (1.05-1.25)
    zoom_factor = 1.05 + (intensity * 0.2)
    
    try:
        if effect == "zoom_in":
            return apply_zoom_in(video, zoom_factor=zoom_factor)
        elif effect == "zoom_out":
            return apply_zoom_out(video, zoom_factor=zoom_factor)
        elif effect == "pan_left":
            return apply_pan_effect(video, direction="left")
        elif effect == "pan_right":
            return apply_pan_effect(video, direction="right")
        elif effect == "ken_burns":
            return apply_ken_burns(video, zoom_start=1.0, zoom_end=zoom_factor)
        elif effect == "zoom_pulse":
            pulses = max(1, int(intensity * 3))
            return apply_zoom_pulse(video, max_zoom=zoom_factor, pulses=pulses)
        elif effect == "shake":
            return apply_shake(video, intensity=intensity * 8)
        elif effect == "vignette":
            return apply_vignette(video, strength=intensity)
        elif effect == "color_shift":
            return apply_color_shift(video, hue_shift=intensity * 0.15)
        elif effect == "rotation":
            return apply_rotation(video, max_angle=intensity * 4)
        elif effect == "flash":
            return apply_brightness_flash(video, flash_at=0.0)
        elif effect == "none":
            return video
        else:
            # Try the named effect helper
            return _apply_effect_by_name(video, effect)
    except Exception as e:
        logger.warning(f"Effect '{effect}' failed: {e}, using fallback")
        return apply_random_effect(video, is_reels)
