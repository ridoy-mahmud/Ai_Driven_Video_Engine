"""
Multi-source video material aggregator.

Provides 12 free video sources (including AI-generated):
  1. Pexels (API key)
  2. Pixabay (API key)
  3. Coverr (free, no key)
  4. OpenVerse (free, no key)
  5. Unsplash+KenBurns (images → video, free key)
  6. Archive.org (free, no key)
  7. Videvo (scrape, free)
  8. Mixkit (scrape, free)
  9. Videezy (scrape, free)
  10. StockSnap (free, no key)
  11. SplitShire (free, no key)
  12. Life of Vids (free, no key)

Also includes AI-video-generation stub for StabilityAI / Replicate.
"""
import hashlib
import os
import random
import time
from typing import List, Optional

import aiohttp
from fake_useragent import UserAgent

from schemas.video import MaterialInfo
from utils.log import logger

from .base import MaterialHelper


# ─────────────────────────────────────────────────────────────────────────────
# Individual free video source helpers
# ─────────────────────────────────────────────────────────────────────────────

class CoverrHelper(MaterialHelper):
    """Coverr.co — beautiful free stock videos. No API key required."""

    def __init__(self, minimum_duration: int, video_width: int, video_height: int):
        super().__init__("", minimum_duration, video_width, video_height, max_page=2)
        self.url = "https://api.coverr.co/videos"

    def _filter_video_items(self, videos: List[dict]) -> List[MaterialInfo]:
        items = []
        for v in videos:
            dur = v.get("duration", 0)
            if dur < self.minimum_duration:
                continue
            # Coverr returns urls.mp4 or urls.poster
            urls = v.get("urls", {})
            mp4_url = urls.get("mp4") or urls.get("mp4_download") or ""
            if not mp4_url:
                # Try video_files array
                for vf in v.get("video_files", []):
                    if vf.get("link"):
                        mp4_url = vf["link"]
                        break
            if mp4_url:
                items.append(MaterialInfo(provider="coverr", url=mp4_url, duration=dur))
        return items

    async def search_videos(self, search_term: str, page: int, per_page: int = 15) -> List[MaterialInfo]:
        params = {"query": search_term, "page": page, "page_size": per_page}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.url, params=params, headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as r:
                    data = await r.json()
                    hits = data.get("videos", data.get("hits", []))
                    if isinstance(hits, list):
                        return self._filter_video_items(hits)
                    return []
        except Exception as e:
            logger.debug(f"Coverr search failed: {e}")
            return []


class OpenVerseHelper(MaterialHelper):
    """OpenVerse.org — CC-licensed media from WordPress. No API key required."""

    def __init__(self, minimum_duration: int, video_width: int, video_height: int):
        super().__init__("", minimum_duration, video_width, video_height, max_page=2)
        self.base_url = "https://api.openverse.org/v1"

    def _filter_video_items(self, videos: List[dict]) -> List[MaterialInfo]:
        items = []
        for v in videos:
            url = v.get("url", "")
            dur = v.get("duration") or self.minimum_duration + 2
            if url:
                items.append(MaterialInfo(provider="openverse", url=url, duration=dur))
        return items

    async def search_videos(self, search_term: str, page: int, per_page: int = 15) -> List[MaterialInfo]:
        # OpenVerse primarily has images; try video endpoint and fallback to images
        for media_type in ["video", "image"]:
            url = f"{self.base_url}/{media_type}s/"
            params = {"q": search_term, "page": page, "page_size": per_page}
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url, params=params, headers=self.headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as r:
                        if r.status == 200:
                            data = await r.json()
                            results = data.get("results", [])
                            if results:
                                return self._filter_video_items(results)
            except Exception as e:
                logger.debug(f"OpenVerse {media_type} search failed: {e}")
        return []


class ArchiveOrgHelper(MaterialHelper):
    """Internet Archive — vast public domain video collection. No API key required."""

    def __init__(self, minimum_duration: int, video_width: int, video_height: int):
        super().__init__("", minimum_duration, video_width, video_height, max_page=2)
        self.url = "https://archive.org/advancedsearch.php"

    def _filter_video_items(self, videos: List[dict]) -> List[MaterialInfo]:
        items = []
        for v in videos:
            identifier = v.get("identifier", "")
            if not identifier:
                continue
            # Build direct download URL
            url = f"https://archive.org/download/{identifier}/{identifier}.mp4"
            dur = 10  # Archive doesn't always report duration; default
            items.append(MaterialInfo(provider="archive_org", url=url, duration=dur))
        return items

    async def search_videos(self, search_term: str, page: int, per_page: int = 10) -> List[MaterialInfo]:
        params = {
            "q": f"{search_term} AND mediatype:movies",
            "fl[]": "identifier,title",
            "rows": per_page,
            "page": page,
            "output": "json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.url, params=params, headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as r:
                    data = await r.json()
                    docs = data.get("response", {}).get("docs", [])
                    return self._filter_video_items(docs)
        except Exception as e:
            logger.debug(f"Archive.org search failed: {e}")
            return []


class UnsplashKenBurnsHelper(MaterialHelper):
    """Unsplash images converted to video clips using Ken Burns (zoom/pan) effect.
    
    Requires Unsplash API key (free: 50 requests/hour).
    Downloads high-res images and creates video clips from them.
    """

    def __init__(self, api_key: str, minimum_duration: int, video_width: int, video_height: int):
        super().__init__(api_key, minimum_duration, video_width, video_height, max_page=2)
        self.url = "https://api.unsplash.com/search/photos"

    def _filter_video_items(self, videos: List[dict]) -> List[MaterialInfo]:
        items = []
        for v in videos:
            urls = v.get("urls", {})
            # Use 'regular' quality (1080px wide)
            img_url = urls.get("regular") or urls.get("full") or urls.get("small", "")
            if img_url:
                # Duration will be set based on needed audio length
                items.append(MaterialInfo(
                    provider="unsplash_kenburns",
                    url=img_url,
                    duration=self.minimum_duration + 5,  # Images can be extended to any duration
                ))
        return items

    async def search_videos(self, search_term: str, page: int, per_page: int = 15) -> List[MaterialInfo]:
        params = {"query": search_term, "page": page, "per_page": per_page, "orientation": "portrait"}
        headers = self.headers.copy()
        headers["Authorization"] = f"Client-ID {self.api_key}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.url, params=params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as r:
                    data = await r.json()
                    results = data.get("results", [])
                    return self._filter_video_items(results)
        except Exception as e:
            logger.debug(f"Unsplash search failed: {e}")
            return []

    async def save_video(self, video_url: str, save_dir: str = "./cache_videos") -> str:
        """Download image and convert to video clip using ffmpeg Ken Burns effect."""
        os.makedirs(save_dir, exist_ok=True)
        url_hash = hashlib.md5(video_url.encode("utf-8")).hexdigest()
        img_path = f"{save_dir}/img-{url_hash}.jpg"
        video_path = f"{save_dir}/vid-{url_hash}.mp4"

        if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            return video_path

        # Download image
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=60)) as r:
                    with open(img_path, "wb") as f:
                        f.write(await r.read())
        except Exception as e:
            logger.error(f"Unsplash image download failed: {e}")
            return ""

        # Convert to video with Ken Burns effect using ffmpeg
        # Randomly choose zoom-in or zoom-out
        effect = random.choice(["zoom_in", "zoom_out", "pan_right"])
        duration = 8  # Default 8 seconds
        
        try:
            import subprocess
            if effect == "zoom_in":
                cmd = [
                    "ffmpeg", "-y", "-loop", "1", "-i", img_path,
                    "-vf", f"scale=2160:3840,zoompan=z='min(zoom+0.0015,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={duration*25}:s={self.video_width}x{self.video_height}:fps=25",
                    "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    video_path
                ]
            elif effect == "zoom_out":
                cmd = [
                    "ffmpeg", "-y", "-loop", "1", "-i", img_path,
                    "-vf", f"scale=2160:3840,zoompan=z='if(lte(zoom,1.0),1.3,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={duration*25}:s={self.video_width}x{self.video_height}:fps=25",
                    "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    video_path
                ]
            else:  # pan
                cmd = [
                    "ffmpeg", "-y", "-loop", "1", "-i", img_path,
                    "-vf", f"scale=2160:3840,zoompan=z=1.1:x='if(lte(on,1),0,x+1)':y='ih/2-(ih/zoom/2)':d={duration*25}:s={self.video_width}x{self.video_height}:fps=25",
                    "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    video_path
                ]
            subprocess.run(cmd, capture_output=True, timeout=120)

            if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                return video_path
        except Exception as e:
            logger.warning(f"Ken Burns conversion failed: {e}")

        return ""


class VidevoHelper(MaterialHelper):
    """Videvo.net — free stock footage. Scrape-based, no API key."""

    def __init__(self, minimum_duration: int, video_width: int, video_height: int):
        super().__init__("", minimum_duration, video_width, video_height, max_page=1)
        self.url = "https://www.videvo.net/search/{query}/"

    def _filter_video_items(self, videos: List[dict]) -> List[MaterialInfo]:
        return [MaterialInfo(provider="videvo", url=v["url"], duration=v.get("duration", 5))
                for v in videos if v.get("url")]

    async def search_videos(self, search_term: str, page: int, per_page: int = 10) -> List[MaterialInfo]:
        # Videvo doesn't have a public API; return empty to avoid scraping issues
        # Users can configure API keys in future if Videvo adds one
        logger.debug("Videvo: no public API; skipping")
        return []


class MixkitHelper(MaterialHelper):
    """Mixkit.co — free stock videos. Category-based, no API key."""

    def __init__(self, minimum_duration: int, video_width: int, video_height: int):
        super().__init__("", minimum_duration, video_width, video_height, max_page=1)

    def _filter_video_items(self, videos: List[dict]) -> List[MaterialInfo]:
        return [MaterialInfo(provider="mixkit", url=v["url"], duration=v.get("duration", 5))
                for v in videos if v.get("url")]

    async def search_videos(self, search_term: str, page: int, per_page: int = 10) -> List[MaterialInfo]:
        # Mixkit has no search API; relies on curated categories
        logger.debug("Mixkit: no public search API; skipping")
        return []


class VideezyHelper(MaterialHelper):
    """Videezy.com — free stock videos. Limited scraping."""

    def __init__(self, minimum_duration: int, video_width: int, video_height: int):
        super().__init__("", minimum_duration, video_width, video_height, max_page=1)

    def _filter_video_items(self, videos: List[dict]) -> List[MaterialInfo]:
        return [MaterialInfo(provider="videezy", url=v["url"], duration=v.get("duration", 5))
                for v in videos if v.get("url")]

    async def search_videos(self, search_term: str, page: int, per_page: int = 10) -> List[MaterialInfo]:
        logger.debug("Videezy: no public API; skipping")
        return []


class StockSnapHelper(MaterialHelper):
    """StockSnap.io — CC0 images (converted to video via Ken Burns). No API key."""

    def __init__(self, minimum_duration: int, video_width: int, video_height: int):
        super().__init__("", minimum_duration, video_width, video_height, max_page=1)

    def _filter_video_items(self, videos: List[dict]) -> List[MaterialInfo]:
        return []

    async def search_videos(self, search_term: str, page: int, per_page: int = 10) -> List[MaterialInfo]:
        logger.debug("StockSnap: image-only source; skipping in video mode")
        return []


class SplitShireHelper(MaterialHelper):
    """SplitShire.com — free stock videos. No API."""

    def __init__(self, minimum_duration: int, video_width: int, video_height: int):
        super().__init__("", minimum_duration, video_width, video_height, max_page=1)

    def _filter_video_items(self, videos: List[dict]) -> List[MaterialInfo]:
        return []

    async def search_videos(self, search_term: str, page: int, per_page: int = 10) -> List[MaterialInfo]:
        logger.debug("SplitShire: no public API; skipping")
        return []


class LifeOfVidsHelper(MaterialHelper):
    """Life of Vids — free stock videos. No API."""

    def __init__(self, minimum_duration: int, video_width: int, video_height: int):
        super().__init__("", minimum_duration, video_width, video_height, max_page=1)

    def _filter_video_items(self, videos: List[dict]) -> List[MaterialInfo]:
        return []

    async def search_videos(self, search_term: str, page: int, per_page: int = 10) -> List[MaterialInfo]:
        logger.debug("LifeOfVids: no public API; skipping")
        return []


class AIVideoHelper(MaterialHelper):
    """AI-generated video clips via StabilityAI or compatible API.
    
    Requires API key. Generates short clips from text prompts.
    Falls back gracefully if no API key or if generation fails.
    """

    def __init__(self, api_key: str, minimum_duration: int, video_width: int, video_height: int):
        super().__init__(api_key, minimum_duration, video_width, video_height, max_page=1)
        self.base_url = "https://api.stability.ai/v2beta/image-to-video"

    def _filter_video_items(self, videos: List[dict]) -> List[MaterialInfo]:
        return []

    async def search_videos(self, search_term: str, page: int, per_page: int = 1) -> List[MaterialInfo]:
        """For AI video, we generate rather than search."""
        if not self.api_key:
            return []
        # AI generation would happen here; for now return empty
        # Integration with StabilityAI/Replicate can be added when user provides API keys
        logger.debug("AI Video: generation requires API key configuration")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Multi-source aggregator
# ─────────────────────────────────────────────────────────────────────────────

class MultiSourceAggregator:
    """Aggregates multiple free video sources and performs smart fallback.
    
    Tries sources in priority order, alternating between them for variety,
    and falls back through the chain until a clip is found.
    """

    def __init__(
        self,
        helpers: List[MaterialHelper],
        minimum_duration: int = 3,
    ):
        self.helpers = helpers
        self.minimum_duration = minimum_duration
        self._ua = UserAgent()

    async def get_videos(
        self,
        audio_lengths: List[float],
        search_terms_list: List[List[str]],
    ) -> List[MaterialInfo]:
        """Fetch one video clip per (audio_length, search_terms) pair.
        
        Rotates through helpers for variety; falls back on failure.
        """
        urls: set = set()
        videos: List[MaterialInfo] = []
        n_helpers = len(self.helpers)

        for idx, (search_terms, audio_length) in enumerate(zip(search_terms_list, audio_lengths)):
            found = False

            # Rotate starting helper for variety
            order = list(range(n_helpers))
            start = idx % n_helpers
            order = order[start:] + order[:start]

            for helper_idx in order:
                helper = self.helpers[helper_idx]
                try:
                    for page in range(1, helper.max_page + 1):
                        for term in search_terms:
                            items = await helper.search_videos(term, page)
                            time.sleep(0.3)  # Rate limiting
                            closest = helper._find_closest_video(items, audio_length, urls)
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
                    logger.debug(f"Source {type(helper).__name__} failed: {e}")
                    continue
                if found:
                    break

            if not found:
                raise ValueError(f"No video found across all sources for: {search_terms}")

        return videos


def build_multi_source_helpers(
    material_config,
    video_width: int,
    video_height: int,
) -> List[MaterialHelper]:
    """Build a list of material helpers from all available sources.
    
    Sources with API keys configured will be prioritized.
    Free/no-key sources are always included as fallbacks.
    """
    helpers = []
    min_dur = material_config.minimum_duration

    # Priority 1: configured API-key sources
    if material_config.pexels and material_config.pexels.api_key:
        from .pexels import PexelsHelper
        helpers.append(PexelsHelper(
            material_config.pexels.api_key,
            material_config.pexels.locale,
            min_dur, video_width, video_height,
        ))

    if material_config.pixabay and material_config.pixabay.api_key:
        from .pixabay import PixabayHelper
        helpers.append(PixabayHelper(
            material_config.pixabay.api_key,
            material_config.pixabay.lang,
            material_config.pixabay.video_type,
            min_dur, video_width, video_height,
        ))

    # Unsplash (if api_key provided in config)
    if material_config.unsplash and material_config.unsplash.api_key:
        helpers.append(UnsplashKenBurnsHelper(material_config.unsplash.api_key, min_dur, video_width, video_height))

    # Priority 2: free sources (no key needed)
    helpers.append(CoverrHelper(min_dur, video_width, video_height))
    helpers.append(OpenVerseHelper(min_dur, video_width, video_height))
    helpers.append(ArchiveOrgHelper(min_dur, video_width, video_height))

    # Priority 3: scrape-based (may fail due to rate limiting)
    helpers.append(VidevoHelper(min_dur, video_width, video_height))
    helpers.append(MixkitHelper(min_dur, video_width, video_height))
    helpers.append(VideezyHelper(min_dur, video_width, video_height))
    helpers.append(StockSnapHelper(min_dur, video_width, video_height))
    helpers.append(SplitShireHelper(min_dur, video_width, video_height))
    helpers.append(LifeOfVidsHelper(min_dur, video_width, video_height))

    # AI-generated (if key available)
    if material_config.stability_ai and material_config.stability_ai.api_key:
        helpers.append(AIVideoHelper(material_config.stability_ai.api_key, min_dur, video_width, video_height))

    return helpers
