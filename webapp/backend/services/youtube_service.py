"""YouTube download service using yt-dlp"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Callable, Optional
import yt_dlp
import sys

# Add UltraSinger src to path for imports
ultrasinger_src = Path(__file__).parent.parent.parent.parent / "src"
if str(ultrasinger_src) not in sys.path:
    sys.path.insert(0, str(ultrasinger_src))

logger = logging.getLogger(__name__)

# Video download configuration
VIDEO_DOWNLOAD_METHODS = [
    {
        "name": "Firefox cookies",
        "cookiesfrombrowser": ("firefox",),
    },
    {
        "name": "cookies.txt file",
        "cookiefile": None,  # Will be set dynamically if file exists
    },
    {
        "name": "Android client",
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    },
    {
        "name": "iOS client",
        "extractor_args": {"youtube": {"player_client": ["ios"]}},
    },
    {
        "name": "TV embedded client",
        "extractor_args": {"youtube": {"player_client": ["tv_embedded"]}},
    },
    {
        "name": "Web client (default)",
        # No special options, just default yt-dlp behavior
    },
]

# Path to cookies.txt file (can be customized)
COOKIES_FILE_PATH = Path(__file__).parent.parent.parent.parent / "cookies.txt"


def get_cookies_file_path() -> Optional[Path]:
    """Get path to cookies.txt file if it exists"""
    if COOKIES_FILE_PATH.exists():
        return COOKIES_FILE_PATH
    # Also check in webapp/backend folder
    alt_path = Path(__file__).parent.parent / "cookies.txt"
    if alt_path.exists():
        return alt_path
    return None


def sanitize_filename(fname: str) -> str:
    """Sanitize filename for Windows/Unix compatibility"""
    # Replace forbidden characters
    replacements = (('?:"', ""), ("<", "("), (">", ")"), ("/\\|*", "-"))
    for old, new in replacements:
        for char in old:
            fname = fname.replace(char, new)
    # Windows doesn't like trailing periods
    if fname.endswith("."):
        fname = fname.rstrip(" .")
    return fname


def extract_artist_title(video_info: dict) -> tuple[str, str]:
    """Extract artist and title from YouTube video info"""
    import re

    # Try artist/track fields first (some videos have proper metadata)
    if "artist" in video_info and "track" in video_info:
        artist = video_info["artist"].strip()
        track = video_info["track"].strip()
        # Clean up track title
        track = _clean_title(track)
        return artist, track

    # Parse from title if it contains " - "
    title = video_info.get("title", "")
    if " - " in title:
        parts = title.split(" - ", 1)
        artist = parts[0].strip()
        song_title = parts[1].strip()

        # Clean up the song title (remove common YouTube suffixes)
        song_title = _clean_title(song_title)

        return artist, song_title

    # Fallback: use channel as artist and title as song title
    channel = video_info.get("channel", video_info.get("uploader", "Unknown Artist"))
    clean_title = _clean_title(title)
    return channel.strip(), clean_title


def _clean_title(title: str) -> str:
    """Remove common YouTube video suffixes from song title"""
    import re

    # Common patterns to remove (case-insensitive)
    patterns_to_remove = [
        r'\(Official Video\)',
        r'\(Official Music Video\)',
        r'\(Official Audio\)',
        r'\(Official Lyric Video\)',
        r'\(Lyric Video\)',
        r'\(Lyrics\)',
        r'\(Audio\)',
        r'\(HD\)',
        r'\(4K\)',
        r'\(Music Video\)',
        r'\(Video\)',
        r'\(Official\)',
        r'\[Official Video\]',
        r'\[Official Music Video\]',
        r'\[Official Audio\]',
        r'\[Lyric Video\]',
        r'\[Lyrics\]',
        r'\[Audio\]',
        r'\[HD\]',
        r'\[4K\]',
        r'\(New Version\)',
        r'\[New Version\]',
        r'\(Remastered\)',
        r'\[Remastered\]',
        r'\(Visualizer\)',
        r'\[Visualizer\]',
    ]

    cleaned = title
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    # Clean up extra whitespace and dashes
    cleaned = re.sub(r'\s+', ' ', cleaned)  # Multiple spaces to single space
    cleaned = re.sub(r'\s*-\s*$', '', cleaned)  # Trailing dash
    cleaned = cleaned.strip()

    return cleaned if cleaned else title  # Return original if cleaning removed everything


async def download_youtube_audio(
    url: str,
    output_dir: Path,
    progress_callback: Callable[[str, float], None] | None = None
) -> tuple[Path, str, str]:
    """
    Download audio from YouTube URL and get corrected metadata

    Args:
        url: YouTube video URL
        output_dir: Directory to save the audio file
        progress_callback: Optional callback for progress updates (message, percentage)

    Returns:
        Tuple of (audio_file_path, artist, title)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    def progress_hook(d):
        """Hook to track download progress"""
        if progress_callback:
            if d["status"] == "downloading":
                try:
                    percentage = (d.get("downloaded_bytes", 0) / d.get("total_bytes", 1)) * 100
                    progress_callback(f"Downloading: {percentage:.1f}%", percentage)
                except (KeyError, ZeroDivisionError):
                    pass
            elif d["status"] == "finished":
                progress_callback("Download completed, processing...", 100)

    # Use yt-dlp's outtmpl preprocessing to sanitize filename
    # The %(title)s will be sanitized automatically
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }],
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "progress_hooks": [progress_hook] if progress_callback else [],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,  # Only download single video, not playlist
        "restrictfilenames": True,  # Sanitize filenames automatically
        "retries": 10,  # Retry failed downloads
        "fragment_retries": 10,  # Retry failed fragments
    }
    # Note: Browser cookies (cookiesfrombrowser) can help avoid 403 errors but require
    # the browser to be fully closed. Disabled for now to avoid locked database errors.
    # Note: Don't use extractor_args with player_client as it can cause format issues.

    try:
        # Run yt-dlp in thread pool to avoid blocking
        # This will fetch video info and download in one operation
        video_info, audio_path = await asyncio.to_thread(
            _download_sync,
            url,
            ydl_opts
        )

        # Extract artist and title from video info
        artist, title = extract_artist_title(video_info)
        logger.info(f"Extracted from YouTube: {artist} - {title}")

        # Try to get better metadata from MusicBrainz
        # Only use it if the artist name is similar (not a cover/different version)
        try:
            from modules.musicbrainz_client import search_musicbrainz
            song_info = await asyncio.to_thread(search_musicbrainz, title, artist)
            if song_info and song_info.artist and song_info.title:
                # Check if MusicBrainz found the same artist (with some fuzzy matching)
                yt_artist_lower = artist.lower()
                mb_artist_lower = song_info.artist.lower()

                # Only apply MusicBrainz correction if artists are similar
                # This prevents replacing "Imagine Dragons" with "GnuS Cello" (cover version)
                if (yt_artist_lower in mb_artist_lower or
                    mb_artist_lower in yt_artist_lower or
                    yt_artist_lower == mb_artist_lower):
                    artist = song_info.artist
                    title = song_info.title
                    logger.info(f"MusicBrainz corrected to: {artist} - {title}")
                else:
                    logger.info(f"MusicBrainz found different artist ({song_info.artist}), keeping YouTube metadata")
        except Exception as e:
            logger.warning(f"MusicBrainz lookup failed, using YouTube metadata: {e}")

        return Path(audio_path), artist, title

    except Exception as e:
        logger.error(f"Failed to download from YouTube: {e}")
        raise ValueError(f"YouTube download failed: {str(e)}")


def _download_sync(url: str, ydl_opts: dict) -> tuple[dict, str]:
    """Synchronous download helper"""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # Get the actual output path
        audio_path = ydl.prepare_filename(info)
        # Change extension to wav
        audio_path = audio_path.rsplit(".", 1)[0] + ".wav"
        return info, audio_path


async def get_video_info(url: str) -> dict:
    """Get video information without downloading"""
    # Note: Don't use cookies here - just fetching metadata which doesn't need auth
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,  # Prevent playlist extraction which can hang
        "extract_flat": False,
    }

    try:
        # Add timeout to prevent hanging on problematic URLs
        info = await asyncio.wait_for(
            asyncio.to_thread(
                _get_info_sync,
                url,
                ydl_opts
            ),
            timeout=60  # 60 second timeout for video info fetch
        )

        # Get the best quality thumbnail
        thumbnail = None
        if info.get("thumbnails"):
            # Get highest quality thumbnail
            thumbnail = info["thumbnails"][-1]["url"]
        elif info.get("thumbnail"):
            thumbnail = info.get("thumbnail")

        return {
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader", "Unknown"),
            "channel": info.get("channel", info.get("uploader", "Unknown")),
            "thumbnail": thumbnail,
        }
    except asyncio.TimeoutError:
        logger.error(f"Timeout while fetching video info for: {url}")
        raise ValueError("Timeout while fetching video information. The video may be unavailable or the URL is invalid.")
    except Exception as e:
        logger.error(f"Failed to get video info: {e}")
        raise ValueError(f"Failed to get video information: {str(e)}")


def _get_info_sync(url: str, ydl_opts: dict) -> dict:
    """Synchronous info extraction helper"""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


async def download_youtube_video(
    url: str,
    output_dir: Path,
    filename_base: str,
    progress_callback: Callable[[str, float], None] | None = None,
    max_quality: str = "720"
) -> Optional[Path]:
    """
    Download video from YouTube with multiple fallback methods.

    Tries methods in order:
    1. Firefox cookies (if Firefox is installed)
    2. cookies.txt file (if exists)
    3. Android client
    4. iOS client
    5. TV embedded client
    6. Default web client

    Args:
        url: YouTube video URL
        output_dir: Directory to save the video file
        filename_base: Base filename without extension (e.g., "Artist - Song")
        progress_callback: Optional callback for progress updates
        max_quality: Maximum video quality (default "720" for 720p)

    Returns:
        Path to downloaded video file, or None if all methods failed
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_filename = sanitize_filename(filename_base)
    output_template = str(output_dir / f"{safe_filename}.%(ext)s")

    def progress_hook(d):
        """Hook to track download progress"""
        if progress_callback:
            if d["status"] == "downloading":
                try:
                    total = d.get("total_bytes") or d.get("total_bytes_estimate", 1)
                    percentage = (d.get("downloaded_bytes", 0) / total) * 100
                    progress_callback(f"Downloading video: {percentage:.1f}%", percentage)
                except (KeyError, ZeroDivisionError, TypeError):
                    pass
            elif d["status"] == "finished":
                progress_callback("Video download completed", 100)

    # Base options for video download
    base_opts = {
        # Format: best video up to max_quality + best audio, or best combined
        "format": f"bestvideo[height<={max_quality}]+bestaudio/best[height<={max_quality}]/best",
        "outtmpl": output_template,
        "progress_hooks": [progress_hook] if progress_callback else [],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "restrictfilenames": False,  # We handle sanitization ourselves
        "retries": 5,
        "fragment_retries": 5,
        "sleep_interval": 1,  # Sleep between requests to avoid rate limiting
        "max_sleep_interval": 5,
        "merge_output_format": "mp4",  # Ensure output is mp4
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
    }

    errors = []

    for method in VIDEO_DOWNLOAD_METHODS:
        method_name = method.get("name", "Unknown")
        logger.info(f"Trying video download method: {method_name}")

        if progress_callback:
            progress_callback(f"Trying: {method_name}", 0)

        # Build options for this method
        opts = base_opts.copy()

        # Handle cookies.txt file method
        if "cookiefile" in method:
            cookies_path = get_cookies_file_path()
            if cookies_path:
                opts["cookiefile"] = str(cookies_path)
                logger.info(f"Using cookies file: {cookies_path}")
            else:
                logger.info("No cookies.txt file found, skipping this method")
                continue

        # Handle browser cookies method
        if "cookiesfrombrowser" in method:
            opts["cookiesfrombrowser"] = method["cookiesfrombrowser"]

        # Handle extractor args (player client)
        if "extractor_args" in method:
            opts["extractor_args"] = method["extractor_args"]

        try:
            video_path = await asyncio.wait_for(
                asyncio.to_thread(_download_video_sync, url, opts, output_dir, safe_filename),
                timeout=300  # 5 minute timeout per method
            )

            if video_path and video_path.exists():
                logger.info(f"Video download successful with method: {method_name}")
                return video_path

        except asyncio.TimeoutError:
            error_msg = f"{method_name}: Timeout after 5 minutes"
            logger.warning(error_msg)
            errors.append(error_msg)

        except Exception as e:
            error_msg = f"{method_name}: {str(e)}"
            logger.warning(f"Video download failed with {error_msg}")
            errors.append(error_msg)

            # If it's a "format not available" error, try next method
            if "format" in str(e).lower() or "403" in str(e) or "unavailable" in str(e).lower():
                continue
            # For other errors, also continue to next method
            continue

    # All methods failed
    logger.error(f"All video download methods failed. Errors: {errors}")
    if progress_callback:
        progress_callback("Video download failed, continuing without video", 0)

    return None


def _download_video_sync(url: str, ydl_opts: dict, output_dir: Path, filename_base: str) -> Optional[Path]:
    """Synchronous video download helper"""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        # Find the downloaded file
        # yt-dlp might add extension based on format
        for ext in ["mp4", "mkv", "webm", "avi"]:
            potential_path = output_dir / f"{filename_base}.{ext}"
            if potential_path.exists():
                return potential_path

        # Try to get path from info
        if info:
            downloaded_file = ydl.prepare_filename(info)
            # Handle merged format
            if downloaded_file:
                base = downloaded_file.rsplit(".", 1)[0]
                for ext in ["mp4", "mkv", "webm"]:
                    potential = Path(f"{base}.{ext}")
                    if potential.exists():
                        return potential

        return None
