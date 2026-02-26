import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from api.schemas import TaskCreate
from schemas.config import LLMSource, MaterialSource, TTSSource, VideoType
from schemas.video import MaterialInfo, VideoTranscript
from services.llm import LLmWriter
from services.yuanbao import YuanBaoClient
from utils.config import config, get_prompt_config, PROMPT_DESCRIPTIONS
from utils.log import logger
from utils.text import split_content_with_punctuation
from utils.url import get_content, parse_url
from utils.video import create_video


@dataclass
class ProcessingFiles:
    """Class to manage file paths for video processing."""

    folder: str

    def __post_init__(self):
        """Initialize all file paths after instance creation."""
        self.script = os.path.join(self.folder, "_transcript.json")
        self.html = os.path.join(self.folder, "_html.txt")
        self.draft = os.path.join(self.folder, "_transcript.txt")
        self.durations = os.path.join(self.folder, "_durations.json")
        self.videos = os.path.join(self.folder, "_videos.json")
        self.terms = os.path.join(self.folder, "_terms.json")
        self.effects = os.path.join(self.folder, "_effects.json")
        self.output = os.path.join(self.folder, "_output.mp4")


class VideoGenerator:
    def __init__(self):
        self.config = config
        self.assistant = self._create_llm_writer()

    def _create_llm_writer(self, llm_source: str = None) -> LLmWriter:
        """Create LLM writer based on selected LLM source.
        
        Supports: vscode (default), openai, gemini, deepseek.
        Falls back to vscode bridge if source config is missing.
        """
        source = llm_source or (self.config.llm.llm_source.value if self.config.llm.llm_source else "vscode")
        
        # Try source-specific config first
        provider_map = {
            "openai": self.config.llm.openai,
            "gemini": self.config.llm.gemini,
            "deepseek": self.config.llm.deepseek,
            "vscode": self.config.llm.vscode,
        }
        
        cfg = provider_map.get(source)
        if cfg and cfg.api_key and cfg.base_url:
            logger.info(f"Using LLM source: {source}")
            return LLmWriter(cfg.api_key, cfg.base_url, cfg.model)
        
        # Fallback to vscode bridge
        if self.config.llm.vscode:
            cfg = self.config.llm.vscode
            logger.info("Falling back to VS Code Copilot bridge")
            return LLmWriter(cfg.api_key, cfg.base_url, cfg.model)
        
        # Final fallback to legacy config fields
        return LLmWriter(self.config.llm.api_key, self.config.llm.base_url, self.config.llm.model)

    async def _get_content_from_source(self, url: str, files: ProcessingFiles) -> Optional[str]:
        """Fetch or read content from URL or direct text."""
        logger.info("Starting to fetch content")
        if os.path.exists(files.html):
            logger.info("Content file already exists, reading from file")
            return self._read_file(files.html)

        yuanbao_start = "yuanbao"
        if url.startswith("http"):
            logger.info("Starting to fetch content from URL")
            content = await get_content(url)
            if not content:
                logger.error("Failed to fetch content from URL")
                return None
        elif url.startswith(yuanbao_start):
            prompt = url[len(yuanbao_start) :]
            yuanbao = YuanBaoClient(self.config.yuanbao)
            content = await yuanbao.get_response([{"role": "user", "content": prompt}])
        else:
            content = url

        self._write_file(files.html, content)
        return content

    async def _generate_transcript(self, content: str, files: ProcessingFiles) -> Optional[str]:
        """Generate first transcript."""
        logger.info("Starting to generate transcrip")
        if os.path.exists(files.draft):
            draft_content = self._read_file(files.draft)
            # Validate cached draft isn't a bridge/provider error message
            error_markers = ["no upstream LLM is configured", "LLM Bridge is running but"]
            if any(marker in draft_content for marker in error_markers):
                logger.warning("Cached draft contains LLM error message, regenerating...")
                os.remove(files.draft)
            else:
                logger.info("transcript file already exists")
                return draft_content

        text_writer = await self.assistant.writer(content, self.config.prompt.prompt_writer)
        if text_writer:
            # Validate the response isn't an error message
            error_markers = ["no upstream LLM is configured", "LLM Bridge is running but"]
            if any(marker in text_writer for marker in error_markers):
                logger.error(f"LLM returned error instead of transcript: {text_writer[:200]}")
                return None
            self._write_file(files.draft, text_writer)
            return text_writer
        return None

    async def _generate_final_transcript(self, transcript: str) -> Optional[Dict[str, Any]]:
        """Generate final video transcript."""
        logger.info("Starting to generate final transcript")

        # Try with response_format first, then retry without if provider doesn't support it
        text_rewriter = None
        for attempt, use_json_format in enumerate([(True,), (False,)], 1):
            kwargs = {}
            if use_json_format[0]:
                kwargs["response_format"] = {"type": "json_object"}
            text_rewriter = await self.assistant.writer(
                transcript,
                self.config.prompt.prompt_rewriter,
                **kwargs,
            )
            if text_rewriter:
                break
            logger.warning(f"LLM attempt {attempt} returned empty response")

        if not text_rewriter:
            logger.error("LLM returned no response after retries")
            return None

        # Detect bridge / provider error messages (no real content)
        bridge_error_markers = [
            "no upstream LLM is configured",
            "LLM Bridge is running but",
            "Set VSCODE_LLM_UPSTREAM_URL",
        ]
        for marker in bridge_error_markers:
            if marker in text_rewriter:
                logger.error(
                    f"LLM returned a bridge error instead of content: {text_rewriter[:200]}"
                )
                return None

        logger.debug(f"LLM rewriter raw response ({len(text_rewriter)} chars): {text_rewriter[:300]}")

        # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
        cleaned = text_rewriter.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n") if "\n" in cleaned else 3
            cleaned = cleaned[first_newline + 1 :]
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3].rstrip()

        # Try direct JSON parse first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Fallback: regex extraction (first { to last })
        json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if not json_match:
            logger.error(f"No JSON object found in LLM response: {text_rewriter[:500]}")
            return None

        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e} | raw: {json_match.group(1)[:300]}")
            return None

    async def _convert_to_transcript(
        self, transcript_data: Dict[str, str | List[Dict[str, str | List[Dict[str, str]]]]]
    ) -> VideoTranscript:
        """Convert transcript data to VideoTranscript"""
        for paragraph in transcript_data["paragraphs"]:
            for dialogue in paragraph["dialogues"]:
                content = dialogue.pop("content")
                dialogue["contents"] = split_content_with_punctuation(content)
        video_transcript = VideoTranscript.model_validate(transcript_data)
        return video_transcript

    async def _process_audio(
        self, video_transcript: VideoTranscript, files: ProcessingFiles, task_create: Optional[TaskCreate] = None
    ) -> List[float]:
        """Process audio for the video."""
        logger.info("Starting to process audio")
        if os.path.exists(files.durations):
            return json.loads(self._read_file(files.durations))

        tts_source = (task_create.tts_source if task_create else None) or self.config.tts.source
        if tts_source == TTSSource.edge:
            from services.tts import EdgeTextToSpeechConverter

            voices = (task_create.tts_voices if task_create and task_create.tts_voices else None) or self.config.tts.edge.voices
            speed = (task_create.tts_speed if task_create and task_create.tts_speed else None) or self.config.tts.edge.speed
            converter = EdgeTextToSpeechConverter(
                voices,
                files.folder,
                speed,
            )
        elif tts_source == TTSSource.kokoro:
            from services.tts.kokoro import KokoroTextToSpeechConverter

            kokoro_cfg = self.config.tts.kokoro
            voices = (task_create.tts_voices if task_create and task_create.tts_voices else None) or (kokoro_cfg.voices if kokoro_cfg else ["af_bella"])
            speed = (task_create.tts_speed if task_create and task_create.tts_speed else None) or (kokoro_cfg.speed if kokoro_cfg else 1.0)
            lang = kokoro_cfg.lang if kokoro_cfg else "en-us"
            converter = KokoroTextToSpeechConverter(
                voices,
                files.folder,
                speed,
                lang,
            )
        else:
            raise ValueError("Invalid TTS source")
        durations = await converter.text_to_speech(video_transcript.paragraphs)
        self._write_json(files.durations, durations)
        return durations

    async def _process_videos(
        self,
        video_transcript: VideoTranscript,
        durations: List[float],
        files: ProcessingFiles,
        material_source: Optional[str] = None,
        video_type: Optional[str] = None,
        effect_plan: Optional[List[Dict[str, Any]]] = None,
    ) -> List[MaterialInfo]:
        """Process videos for the final output.
        
        For reels, uses LLM effect plan num_clips to fetch multiple clips per paragraph
        for quick-cut editing (3-6+ clips minimum).
        """
        logger.info("Starting to process videos")
        if os.path.exists(files.videos):
            datas = json.loads(self._read_file(files.videos))
            return [MaterialInfo.model_validate(data) for data in datas]

        search_terms = await self._get_search_terms(video_transcript, files)

        # For reels, expand clips based on LLM effect plan or default to 2-3x
        is_reels = (video_type == VideoType.reels or video_type == "reels")
        if is_reels:
            expanded_terms = []
            expanded_durations = []
            
            for idx, terms in enumerate(search_terms):
                # Use LLM-planned num_clips if available, otherwise default to 2-3
                num_clips = 2
                if effect_plan and idx < len(effect_plan):
                    num_clips = max(2, effect_plan[idx].get("num_clips", 2))
                
                for _ in range(num_clips):
                    expanded_terms.append(terms)
                
                # Split duration evenly across clips
                dur = durations[idx] if idx < len(durations) else durations[-1]
                clip_dur = dur / num_clips
                for _ in range(num_clips):
                    expanded_durations.append(clip_dur)
            
            search_terms = expanded_terms
            durations = expanded_durations
            
            # Ensure minimum 3 clips total for reels
            total_clips = len(search_terms)
            if total_clips < 3 and len(search_terms) > 0:
                while len(search_terms) < 3:
                    search_terms.append(search_terms[-1])
                    durations.append(durations[-1])
            
            logger.info(f"Reels: expanded to {len(search_terms)} clip search terms")

        material_source = material_source or self.config.material.source

        # Create material helpers based on source
        if material_source == MaterialSource.all:
            # Use ALL available sources with smart fallback chain
            from services.material import build_multi_source_helpers, MultiSourceAggregator

            helpers = build_multi_source_helpers(
                self.config.material,
                self.config.video.width,
                self.config.video.height,
            )
            aggregator = MultiSourceAggregator(helpers, self.config.material.minimum_duration)
            videos = await aggregator.get_videos(durations, search_terms)
            logger.info(f"All sources: fetched {len(videos)} clips total")

        elif material_source == MaterialSource.both:
            # Use both Pexels AND Pixabay: try Pexels first, fallback to Pixabay
            from services.material import PexelsHelper, PixabayHelper

            pexels_helper = PexelsHelper(
                self.config.material.pexels.api_key,
                self.config.material.pexels.locale,
                self.config.material.minimum_duration,
                self.config.video.width,
                self.config.video.height,
            )
            pixabay_helper = PixabayHelper(
                self.config.material.pixabay.api_key,
                self.config.material.pixabay.lang,
                self.config.material.pixabay.video_type,
                self.config.material.minimum_duration,
                self.config.video.width,
                self.config.video.height,
            )

            # Alternate between sources and use fallback on failure
            videos = []
            urls = set()
            for idx, (terms, dur) in enumerate(zip(search_terms, durations)):
                found = False
                # Alternate: even idx → Pexels first, odd idx → Pixabay first
                primary = pexels_helper if idx % 2 == 0 else pixabay_helper
                fallback = pixabay_helper if idx % 2 == 0 else pexels_helper
                
                for helper in [primary, fallback]:
                    try:
                        for search_term in terms:
                            video_items = await helper.search_videos(search_term, 1)
                            closest = helper._find_closest_video(video_items, dur, urls)
                            if closest:
                                urls.add(closest.url)
                                video_path = await helper.save_video(closest.url)
                                if video_path:
                                    closest.video_path = video_path
                                    videos.append(closest)
                                    found = True
                                    break
                        if found:
                            break
                    except Exception as e:
                        logger.warning(f"Material source failed for term {terms}: {e}, trying fallback")
                        continue
                
                if not found:
                    raise ValueError(f"No video found for search terms: {terms}")
            
            logger.info(f"Both sources: fetched {len(videos)} clips total")

        elif material_source == MaterialSource.pexels:
            from services.material import PexelsHelper

            material_helper = PexelsHelper(
                self.config.material.pexels.api_key,
                self.config.material.pexels.locale,
                self.config.material.minimum_duration,
                self.config.video.width,
                self.config.video.height,
            )
            videos = await material_helper.get_videos(durations, search_terms)

        elif material_source == MaterialSource.pixabay:
            from services.material import PixabayHelper

            material_helper = PixabayHelper(
                self.config.material.pixabay.api_key,
                self.config.material.pixabay.lang,
                self.config.material.pixabay.video_type,
                self.config.material.minimum_duration,
                self.config.video.width,
                self.config.video.height,
            )
            videos = await material_helper.get_videos(durations, search_terms)
        else:
            raise ValueError("Invalid material source")

        self._write_json(files.videos, [video.model_dump() for video in videos])
        return videos

    async def _get_search_terms(
        self, video_transcript: VideoTranscript, files: ProcessingFiles, max_retries: int = 3
    ) -> List[str]:
        """Get search terms for video content."""
        logger.info("Starting to get search terms")
        if os.path.exists(files.terms):
            return json.loads(self._read_file(files.terms))

        content_list = []
        i = 0
        for paragraph in video_transcript.paragraphs:
            dialogues = paragraph.dialogues
            contents = []
            for dialogue in dialogues:
                contents.extend(dialogue.contents)
            content_list.append({"id": i + 1, "content": "\n".join(contents)})

        for i in range(max_retries):
            logger.debug(f"Trying to get search terms {i+1}/{max_retries}")
            content = await self.assistant.writer(
                str(content_list), self.config.material.prompt, response_format={"type": "json_object"}
            )
            json_match = re.search(r"(\[.*\s?\])", content, re.DOTALL)
            if not json_match:
                logger.warning("No valid JSON found in search terms response")
                continue
            results = json.loads(json_match.group(1))
            if len(results) != len(content_list):
                logger.warning("Number of search terms does not match number of dialogues")
                continue
            try:
                search_terms = [result["search_terms"] for result in results]
                break
            except KeyError:
                logger.warning("Invalid search terms response")
                continue
        else:
            raise ValueError("Number of search terms does not match number of dialogues")
        self._write_json(files.terms, search_terms)
        return search_terms

    async def _plan_effects(
        self, video_transcript: VideoTranscript, files: ProcessingFiles, video_type: str = "short_content"
    ) -> List[Dict[str, Any]]:
        """Ask LLM to analyze the transcript and plan video effects per paragraph.
        
        Returns a list of effect plans, one per paragraph, with:
        - transition: slide_left, slide_right, crossfade, none
        - effect: zoom_in, zoom_out, pan_left, pan_right, none
        - intensity: 0.0-1.0 (how strong the effect should be)
        - clip_style: dramatic, calm, fast, emotional
        """
        logger.info("Starting LLM effect planning")
        if os.path.exists(files.effects):
            return json.loads(self._read_file(files.effects))

        is_reels = (video_type == "reels")

        # Build content summary for LLM
        paragraphs_summary = []
        for i, p in enumerate(video_transcript.paragraphs):
            content_lines = []
            for d in p.dialogues:
                content_lines.extend(d.contents)
            paragraphs_summary.append({
                "paragraph_id": i + 1,
                "description": p.description,
                "content_preview": " ".join(content_lines)[:200],
                "num_dialogues": len(p.dialogues),
            })

        type_hint = "REELS (12-30s, fast-paced, 3-6+ quick clips)" if is_reels else (
            "SHORT (1-2min, engaging)" if video_type == "short_content" else "MID (5-10min, detailed)"
        )

        effects_prompt = f"""You are a professional video editor AI. Analyze this video transcript and choose the BEST visual effects for each paragraph to maximize viewer engagement.

Video type: {type_hint}
Total paragraphs: {len(paragraphs_summary)}

Transcript paragraphs:
{json.dumps(paragraphs_summary, ensure_ascii=False, indent=2)}

For EACH paragraph, choose:
1. "transition": one of ["crossfade", "slide_left", "slide_right", "slide_up", "none"]
2. "effect": one of ["zoom_in", "zoom_out", "pan_left", "pan_right", "ken_burns", "zoom_pulse", "shake", "vignette", "color_shift", "rotation", "flash", "none"]
3. "intensity": float 0.1 to 1.0 (how dramatic the effect should be)
4. "clip_style": one of ["dramatic", "calm", "fast", "emotional", "energetic"]
5. "num_clips": integer, how many B-roll clips to use (reels: 2-4 per paragraph, others: 1-2)

Effect descriptions:
- zoom_in: Gradual zoom into center (dramatic reveals, emphasis)
- zoom_out: Start zoomed, pull back (context reveal, establishing shots)
- pan_left / pan_right: Horizontal camera pan (scene scanning, movement)
- ken_burns: Combined zoom + pan from corner to corner (documentary-style, photos)
- zoom_pulse: Rhythmic zoom in/out like a heartbeat (music beats, energy)
- shake: Subtle camera shake (urgency, action, breaking news)
- vignette: Dark edges for cinematic look (moody, artistic)
- color_shift: Gradual warm-to-cool color shift (atmosphere, passage of time)
- rotation: Gentle frame rotation (dynamic, playful)
- flash: Brief brightness flash (transitions, emphasis, surprise)

Rules:
- For REELS: use fast transitions, strong effects, high intensity (0.7+), and 2-4 clips per paragraph
- For dramatic/emotional moments: use zoom_in or ken_burns with high intensity
- For calm/explanatory parts: use gentle pan, vignette, or no effect
- For high-energy/exciting parts: use zoom_pulse, shake, or flash
- Vary the effects - don't repeat the same effect consecutively
- First paragraph should have an impactful opener (zoom_in, ken_burns, or flash)
- Match the effect mood to the content

Return JSON array:
[{{
  "paragraph_id": 1,
  "transition": "crossfade",
  "effect": "ken_burns",
  "intensity": 0.8,
  "clip_style": "dramatic",
  "num_clips": 2
}}]"""

        try:
            result = await self.assistant.writer(
                effects_prompt,
                "You are a video editing AI. Return ONLY a valid JSON array.",
                response_format={"type": "json_object"},
            )
            if result:
                json_match = re.search(r"(\[.*\s?\])", result, re.DOTALL)
                if json_match:
                    effects = json.loads(json_match.group(1))
                    # Validate length
                    if len(effects) == len(video_transcript.paragraphs):
                        self._write_json(files.effects, effects)
                        return effects
        except Exception as e:
            logger.warning(f"LLM effect planning failed: {e}, using defaults")

        # Fallback: generate reasonable defaults
        default_effects = []
        effect_cycle = ["zoom_in", "ken_burns", "pan_left", "zoom_pulse", "zoom_out", "vignette", "pan_right", "shake"]
        trans_cycle = ["crossfade", "slide_left", "slide_right", "crossfade", "slide_up"]
        for i in range(len(video_transcript.paragraphs)):
            default_effects.append({
                "paragraph_id": i + 1,
                "transition": trans_cycle[i % len(trans_cycle)] if i > 0 else "none",
                "effect": effect_cycle[i % len(effect_cycle)],
                "intensity": 0.8 if is_reels else 0.5,
                "clip_style": "energetic" if is_reels else "calm",
                "num_clips": 3 if is_reels else 1,
            })
        self._write_json(files.effects, default_effects)
        return default_effects

    @staticmethod
    def _read_file(filepath: str) -> str:
        """Read content from a file."""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _write_file(filepath: str, content: str) -> None:
        """Write content to a file."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _write_json(filepath: str, content: Any) -> None:
        """Write JSON content to a file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=4)

    async def generate_video(self, task_create: TaskCreate, doc_id: Optional[int] = None) -> Optional[str]:
        """Main method to generate video from URL or text content."""
        try:
            url = task_create.name
            logger.info(f"Starting video generation for {url}")
            folder = parse_url(url, doc_id)
            files = ProcessingFiles(folder)

            # Determine video type and speed
            video_type = task_create.video_type or "short_content"
            video_speed = task_create.video_speed
            if video_speed is None:
                # Default speeds per video type
                if video_type == "reels":
                    video_speed = 1.3
                else:
                    video_speed = 1.0

            # Early return if output already exists
            if os.path.exists(files.output):
                logger.info("Output video already exists")
                return files.output

            # Process content and generate transcript
            if not os.path.exists(files.script):
                # Auto-select prompt source if set to "auto"
                prompt_source = task_create.prompt_source
                if prompt_source == "auto":
                    content_preview = url[:500] if not url.startswith("http") else url
                    prompt_source = await self._auto_select_prompt(content_preview)
                    logger.info(f"Auto-selected prompt source: {prompt_source}")

                self.config.prompt = get_prompt_config(prompt_source)
                if task_create.llm_source:
                    self.assistant = self._create_llm_writer(task_create.llm_source)

                content = await self._get_content_from_source(url, files)
                if not content:
                    raise ValueError("Failed to fetch content from source")

                # If auto and we only had URL before, re-select with actual content
                if task_create.prompt_source == "auto" and url.startswith("http"):
                    prompt_source = await self._auto_select_prompt(content[:500])
                    self.config.prompt = get_prompt_config(prompt_source)
                    logger.info(f"Auto re-selected prompt source with content: {prompt_source}")

                # Augment content with duration guidance based on video type
                duration_guidance = self._get_duration_guidance(video_type)
                augmented_content = f"{duration_guidance}\n\n{content}"

                transcript = await self._generate_transcript(augmented_content, files)
                if not transcript:
                    raise ValueError("Failed to generate transcript")

                final_transcript = await self._generate_final_transcript(transcript)
                if not final_transcript:
                    raise ValueError("Failed to generate final transcript")

                self._write_json(files.script, final_transcript)
                logger.info("Video script generation completed, continuing to audio/video...")

            # Load transcript and process
            transcript_data = json.loads(self._read_file(files.script))
            video_transcript = await self._convert_to_transcript(transcript_data)

            # LLM-driven effect planning: analyze transcript and choose effects per paragraph
            effect_plan = await self._plan_effects(video_transcript, files, video_type)
            logger.info(f"Effect plan: {json.dumps(effect_plan, indent=2)}")

            # Generate audio and video
            durations = await self._process_audio(video_transcript, files, task_create)
            videos = await self._process_videos(
                video_transcript, durations, files, task_create.material_source, video_type, effect_plan
            )

            # Create final video with type, speed, and LLM-chosen effects
            await create_video(
                videos, video_transcript, files.folder, files.output, self.config.video,
                video_type=video_type,
                video_speed=video_speed,
                effect_plan=effect_plan,
            )

            # Generate YouTube SEO title for the output
            youtube_meta_path = os.path.join(files.folder, "_youtube_meta.json")
            if not os.path.exists(youtube_meta_path):
                try:
                    youtube_meta = await self._generate_youtube_meta(video_transcript, video_type)
                    self._write_json(youtube_meta_path, youtube_meta)
                    logger.info(f"YouTube meta generated: {youtube_meta.get('title', 'N/A')}")
                except Exception as e:
                    logger.warning(f"YouTube meta generation failed: {e}")

            return files.output if os.path.exists(files.output) else None

        except Exception as e:
            logger.error(f"Error in video generation: {str(e)}")
            raise e

    async def generate_video_from_upload(self, task_create: TaskCreate, doc_id: Optional[int] = None) -> Optional[str]:
        """Generate a new social-media-ready video from an uploaded video.
        
        Pipeline:
        1. Extract keyframes from uploaded video using ffmpeg
        2. Send frames to LLM (Gemini/OpenAI with vision) to understand the content
        3. Generate a social-media-ready script from the analysis
        4. Add TTS voiceover and karaoke subtitles
        5. Export with YouTube SEO title
        """
        try:
            upload_path = task_create.video_upload_path
            if not upload_path or not os.path.exists(upload_path):
                raise ValueError(f"Upload video not found: {upload_path}")

            logger.info(f"Starting video remix from upload: {upload_path}")
            folder = parse_url(f"upload_{os.path.basename(upload_path)}", doc_id)
            files = ProcessingFiles(folder)

            video_type = task_create.video_type or "short_content"
            video_speed = task_create.video_speed or (1.3 if video_type == "reels" else 1.0)

            if os.path.exists(files.output):
                logger.info("Remix output already exists")
                return files.output

            # Set up LLM
            if task_create.llm_source:
                self.assistant = self._create_llm_writer(task_create.llm_source)

            # Step 1: Analyze uploaded video with LLM
            if not os.path.exists(files.script):
                analysis = await self._analyze_uploaded_video(upload_path, files)
                if not analysis:
                    raise ValueError("Failed to analyze uploaded video")

                # Step 2: Auto-select best prompt or use specified
                prompt_source = task_create.prompt_source
                if prompt_source == "auto" or not prompt_source:
                    prompt_source = await self._auto_select_prompt(analysis[:500])
                    logger.info(f"Auto-selected prompt for upload: {prompt_source}")
                
                self.config.prompt = get_prompt_config(prompt_source)

                # Step 3: Generate social-media script from analysis
                duration_guidance = self._get_duration_guidance(video_type)
                script_prompt = (
                    f"{duration_guidance}\n\n"
                    f"Based on this video analysis, create an engaging social media script:\n\n"
                    f"{analysis}\n\n"
                    f"Make it viral-worthy, with hooks, emotional beats, and a strong CTA."
                )

                transcript = await self._generate_transcript(script_prompt, files)
                if not transcript:
                    raise ValueError("Failed to generate script from video analysis")

                final_transcript = await self._generate_final_transcript(transcript)
                if not final_transcript:
                    raise ValueError("Failed to finalize transcript")

                self._write_json(files.script, final_transcript)

            # Load transcript
            transcript_data = json.loads(self._read_file(files.script))
            video_transcript = await self._convert_to_transcript(transcript_data)

            # Effect planning
            effect_plan = await self._plan_effects(video_transcript, files, video_type)

            # Generate audio
            durations = await self._process_audio(video_transcript, files, task_create)

            # Use the uploaded video as source material (cut into clips per paragraph)
            videos = await self._create_clips_from_upload(upload_path, durations, files)

            # Create final video
            await create_video(
                videos, video_transcript, files.folder, files.output, self.config.video,
                video_type=video_type,
                video_speed=video_speed,
                effect_plan=effect_plan,
            )

            # Generate YouTube meta
            youtube_meta_path = os.path.join(files.folder, "_youtube_meta.json")
            if not os.path.exists(youtube_meta_path):
                try:
                    youtube_meta = await self._generate_youtube_meta(video_transcript, video_type)
                    self._write_json(youtube_meta_path, youtube_meta)
                    logger.info(f"YouTube meta generated: {youtube_meta.get('title', 'N/A')}")
                except Exception as e:
                    logger.warning(f"YouTube meta generation failed: {e}")

            return files.output if os.path.exists(files.output) else None

        except Exception as e:
            logger.error(f"Error in video remix: {str(e)}")
            raise e

    async def _auto_select_prompt(self, content_preview: str) -> str:
        """Use LLM to automatically select the best prompt source based on content."""
        descriptions_str = "\n".join(
            f"- {name}: {desc}" for name, desc in PROMPT_DESCRIPTIONS.items()
        )
        
        selection_prompt = f"""You are a content classifier. Based on the content preview below, select the SINGLE BEST matching prompt template from this list:

{descriptions_str}

Content preview:
{content_preview[:500]}

Return ONLY the prompt name (e.g., "tech_talk" or "motivation"). Nothing else."""

        try:
            result = await self.assistant.writer(
                selection_prompt,
                "You are a content classifier. Return ONLY the prompt name, nothing else.",
            )
            if result:
                # Clean the result and validate
                selected = result.strip().strip('"').strip("'").lower().replace(" ", "_")
                if selected in PROMPT_DESCRIPTIONS:
                    return selected
                # Fuzzy match: find closest
                for key in PROMPT_DESCRIPTIONS:
                    if key in selected or selected in key:
                        return key
        except Exception as e:
            logger.warning(f"Auto prompt selection failed: {e}")
        
        return "science_explainer"  # Default fallback

    async def _analyze_uploaded_video(self, video_path: str, files: ProcessingFiles) -> Optional[str]:
        """Analyze an uploaded video by extracting keyframes and sending to LLM.
        
        Uses ffmpeg to extract frames, then sends to the LLM for content understanding.
        """
        import subprocess
        import base64
        
        analysis_file = os.path.join(files.folder, "_video_analysis.txt")
        if os.path.exists(analysis_file):
            return self._read_file(analysis_file)
        
        # Extract keyframes using ffmpeg (1 frame per 2 seconds, max 10 frames)
        frames_dir = os.path.join(files.folder, "_frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        try:
            # Get video duration first
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ]
            duration_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            video_duration = float(duration_result.stdout.strip()) if duration_result.stdout.strip() else 30.0
            
            # Extract frames at intervals
            num_frames = min(10, max(3, int(video_duration / 2)))
            interval = video_duration / num_frames
            
            extract_cmd = [
                "ffmpeg", "-y", "-i", video_path,
                "-vf", f"fps=1/{interval:.1f},scale=640:-1",
                "-frames:v", str(num_frames),
                "-q:v", "3",
                os.path.join(frames_dir, "frame_%03d.jpg")
            ]
            subprocess.run(extract_cmd, capture_output=True, timeout=60)
            
            # Also extract audio for content understanding
            audio_path = os.path.join(files.folder, "_upload_audio.mp3")
            if not os.path.exists(audio_path):
                audio_cmd = [
                    "ffmpeg", "-y", "-i", video_path,
                    "-vn", "-acodec", "libmp3lame", "-q:a", "4",
                    audio_path
                ]
                subprocess.run(audio_cmd, capture_output=True, timeout=60)
            
        except Exception as e:
            logger.warning(f"Frame extraction failed: {e}")
        
        # Collect extracted frames as base64 for vision LLM
        frame_files = sorted([
            os.path.join(frames_dir, f) for f in os.listdir(frames_dir)
            if f.endswith(('.jpg', '.png'))
        ])
        
        if not frame_files:
            # Fallback: just describe based on filename
            analysis = f"Video file: {os.path.basename(video_path)}, Duration: ~{video_duration:.0f}s"
            self._write_file(analysis_file, analysis)
            return analysis
        
        # Build a text-based description prompt (works with any LLM)
        # For vision-capable LLMs, we'd send images; for text-only, describe what we know
        frame_descriptions = f"Extracted {len(frame_files)} keyframes from a {video_duration:.0f}-second video."
        
        # Try to use vision API if available (OpenAI/Gemini style)
        try:
            frames_b64 = []
            for fp in frame_files[:6]:  # Max 6 frames to stay within token limits
                with open(fp, "rb") as f:
                    frames_b64.append(base64.b64encode(f.read()).decode("utf-8"))
            
            # Build vision message
            vision_content = [
                {"type": "text", "text": (
                    "Analyze this video's keyframes thoroughly. Describe:\n"
                    "1. Main subject and topic of the video\n"
                    "2. Visual style and quality\n"
                    "3. Key moments and transitions\n"
                    "4. Overall mood and tone\n"
                    "5. Target audience\n"
                    "6. Suggested social media angle (what makes it shareable)\n\n"
                    "Be detailed and specific."
                )}
            ]
            for b64 in frames_b64:
                vision_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })
            
            # Use the OpenAI-compatible client directly for vision
            response = self.assistant.client.chat.completions.create(
                model=self.assistant.model,
                messages=[
                    {"role": "system", "content": "You are a professional video analyst for social media content creation."},
                    {"role": "user", "content": vision_content}
                ],
                max_tokens=1500,
            )
            
            if response.choices and response.choices[0].message.content:
                analysis = response.choices[0].message.content
                self._write_file(analysis_file, analysis)
                return analysis
                
        except Exception as e:
            logger.warning(f"Vision analysis failed: {e}, falling back to text-only analysis")
        
        # Fallback: text-only analysis based on filename and duration
        fallback_prompt = (
            f"I have a video file '{os.path.basename(video_path)}' that is {video_duration:.0f} seconds long. "
            f"I extracted {len(frame_files)} keyframes. "
            f"Based on the filename and duration, suggest what this video might be about "
            f"and create a compelling social media script concept for it. "
            f"Focus on making it engaging, shareable, and suitable for YouTube/TikTok/Instagram."
        )
        
        analysis = await self.assistant.writer(
            fallback_prompt,
            "You are a social media content strategist. Analyze video content and suggest engaging scripts.",
        )
        
        if analysis:
            self._write_file(analysis_file, analysis)
            return analysis
        
        return None

    async def _create_clips_from_upload(
        self, video_path: str, durations: List[float], files: ProcessingFiles
    ) -> List[MaterialInfo]:
        """Split the uploaded video into clips matching the paragraph durations."""
        import subprocess
        
        if os.path.exists(files.videos):
            datas = json.loads(self._read_file(files.videos))
            return [MaterialInfo.model_validate(data) for data in datas]
        
        # Get total video duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        total_duration = float(result.stdout.strip()) if result.stdout.strip() else sum(durations)
        
        clips = []
        current_time = 0.0
        total_needed = sum(durations)
        
        # Scale durations to fit video length if needed
        scale_factor = total_duration / total_needed if total_needed > total_duration else 1.0
        
        for idx, dur in enumerate(durations):
            scaled_dur = dur * scale_factor
            clip_path = os.path.join(files.folder, f"_upload_clip_{idx:03d}.mp4")
            
            if not os.path.exists(clip_path):
                # Extract clip segment
                clip_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(current_time),
                    "-i", video_path,
                    "-t", str(scaled_dur),
                    "-c:v", "libx264", "-preset", "fast",
                    "-an",  # Remove audio (we'll add TTS)
                    clip_path
                ]
                subprocess.run(clip_cmd, capture_output=True, timeout=120)
            
            clip = MaterialInfo(
                provider="upload",
                url=video_path,
                duration=scaled_dur,
                video_path=clip_path,
            )
            clips.append(clip)
            current_time += scaled_dur
            
            # Loop back if we've reached the end of the source video
            if current_time >= total_duration:
                current_time = 0.0
        
        self._write_json(files.videos, [c.model_dump() for c in clips])
        return clips

    async def _generate_youtube_meta(self, video_transcript: VideoTranscript, video_type: str = "short_content") -> Dict[str, str]:
        """Generate YouTube SEO-optimized title, description, and tags using LLM."""
        # Collect all transcript text
        all_text = []
        for p in video_transcript.paragraphs:
            for d in p.dialogues:
                all_text.extend(d.contents)
        transcript_text = " ".join(all_text)[:1000]
        
        type_hint = {
            "reels": "YouTube Shorts / TikTok / Instagram Reels (12-30s)",
            "short_content": "YouTube Short Video (1-2 min)",
            "mid_content": "YouTube Video (5-10 min)"
        }.get(video_type, "YouTube Video")
        
        meta_prompt = f"""You are a YouTube SEO expert. Generate optimized metadata for this video.

Video type: {type_hint}
Transcript excerpt: {transcript_text}

Generate:
1. "title": A catchy, SEO-friendly YouTube title (max 70 chars). Use power words, numbers, or questions.
2. "description": YouTube description (150-300 chars) with keywords and a call-to-action.
3. "tags": Comma-separated list of 10-15 relevant YouTube tags/keywords.
4. "hashtags": 5 trending hashtags for the video.

Return as JSON object: {{"title": "...", "description": "...", "tags": "...", "hashtags": "..."}}"""

        try:
            result = await self.assistant.writer(
                meta_prompt,
                "You are a YouTube SEO expert. Return ONLY valid JSON.",
                response_format={"type": "json_object"},
            )
            if result:
                json_match = re.search(r"\{.*\}", result, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
        except Exception as e:
            logger.warning(f"YouTube meta generation failed: {e}")
        
        # Fallback
        return {
            "title": transcript_text[:60] + "..." if len(transcript_text) > 60 else transcript_text,
            "description": f"Watch this amazing {video_type.replace('_', ' ')} video!",
            "tags": "video, content, social media, trending",
            "hashtags": "#shorts #viral #trending #fyp #content"
        }

    @staticmethod
    def _get_duration_guidance(video_type: str) -> str:
        """Return prompt guidance to control output duration based on video type."""
        guidance = {
            "reels": (
                "[DURATION CONSTRAINT: This is a SHORT REEL video (12-30 seconds). "
                "Keep the script VERY concise — maximum 2-3 short paragraphs with 1-2 sentences each. "
                "Use punchy, attention-grabbing language. Get straight to the point. "
                "Total spoken content should be under 30 seconds when read aloud.]"
            ),
            "short_content": (
                "[DURATION CONSTRAINT: This is a SHORT video (1-2 minutes). "
                "Keep the script moderate — about 3-5 paragraphs with clear, engaging dialogue. "
                "Total spoken content should be around 1-2 minutes when read aloud.]"
            ),
            "mid_content": (
                "[DURATION CONSTRAINT: This is a MID-LENGTH explanatory video (5-10 minutes). "
                "Create a detailed, comprehensive script with 8-15 paragraphs. "
                "Include thorough explanations, examples, and engaging discussion. "
                "Total spoken content should be around 5-10 minutes when read aloud.]"
            ),
        }
        return guidance.get(video_type, guidance["short_content"])
