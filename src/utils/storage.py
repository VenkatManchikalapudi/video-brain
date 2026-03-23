"""Utilities for saving and managing uploaded files.

This module provides functions for handling file uploads and downloads,
with support for direct MP4 links and YouTube videos via yt-dlp.

Notes:
- For production use, consider storing uploads in cloud storage
  (e.g., GCS, S3) and avoid keeping large files on the app server.
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests

from .cache import cached

try:
    from yt_dlp import YoutubeDL
except ImportError:
    YoutubeDL = None

from services.transcript_service import get_transcript_service

logger = logging.getLogger(__name__)



def save_temp_file(uploaded_file) -> str:
    """Save an uploaded Streamlit file to a temporary local folder.

    Args:
        uploaded_file: The file object returned by st.file_uploader

    Returns:
        Absolute path to the saved file as a string

    Notes:
        - Uses getbuffer() for efficiency when available
        - Falls back to read() if getbuffer() is not available
    """
    from config import config
    
    temp_dir = Path(config.temp_upload_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    fname = getattr(uploaded_file, "name", None) or f"upload_{int(time.time())}.mp4"
    out_path = temp_dir / fname

    try:
        with open(out_path, "wb") as f:
            try:
                f.write(uploaded_file.getbuffer())
            except AttributeError:
                f.write(uploaded_file.read())
        logger.info(f"File saved: {out_path}")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise

    return str(out_path)


def save_from_url(url: str, timeout: int = 30) -> Optional[str]:
    """Download a video from a URL and save it locally.

    Supports:
    - YouTube URLs (downloaded via yt-dlp)
    - Direct MP4 links (HTTP/HTTPS)

    Args:
        url: URL to the video
        timeout: HTTP request timeout in seconds

    Returns:
        Path to the downloaded file, or None on failure
    """
    from config import config
    
    try:
        # Try to download YouTube URLs
        if YoutubeDL is not None and ("youtube.com" in url or "youtu.be" in url):
            try:
                logger.info(f"Downloading YouTube URL: {url}")
                
                temp_dir = Path(config.temp_upload_dir)
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                # Output template for downloaded file
                output_template = str(temp_dir / "youtube_%(id)s.%(ext)s")
                
                # First, try to extract video info and check availability
                info_only_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "socket_timeout": timeout,
                }
                
                try:
                    logger.debug("Checking video availability...")
                    with YoutubeDL(info_only_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        video_id = info.get('id', 'unknown')
                        title = info.get('title', 'Unknown')
                        is_available = info.get('is_available', True)
                        age_restricted = info.get('age_limit', 0) > 0
                        
                        logger.info(f"Video: {title} (ID: {video_id})")
                        
                        if not is_available:
                            logger.error("Video is not available")
                            return None
                        
                        if age_restricted:
                            logger.warning(f"Video is age-restricted (limit: {info.get('age_limit')})")
                except Exception as check_err:
                    logger.debug(f"Video info check failed: {str(check_err)[:100]}")
                
                # Try multiple format options to maximize compatibility
                for format_spec in [
                    "best[ext=mp4]/best[vcodec=h264]/best",  # Prefer MP4 with h264
                    "best[height<=720]",  # Accept 720p or lower
                    "best[vcodec!=av01]",  # Avoid AV1 codec issues
                    "18",  # Fallback to YouTube-safe format 18 (360p MP4)
                    "best",  # Last resort: absolutely best available
                ]:
                    try:
                        logger.info(f"Trying format: {format_spec}")
                        ydl_opts = {
                            "format": format_spec,
                            "outtmpl": output_template,
                            "quiet": False,
                            "no_warnings": False,
                            "socket_timeout": timeout,
                            "skip_unavailable_fragments": True,  # Skip missing HLS fragments
                            "fragment_retries": 3,  # Retry fragments
                            "http_headers": {
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                            },
                            "geo_bypass": True,  # Try to bypass geo-restrictions
                            "extractor_args": {
                                "youtube": {
                                    "innertube_client_version": ["19.09.02"]
                                }
                            }
                        }
                        
                        with YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(url, download=True)
                            
                            if isinstance(info, dict):
                                video_file = ydl.prepare_filename(info)
                                if os.path.exists(video_file):
                                    file_size = os.path.getsize(video_file)
                                    logger.info(f"Downloaded file size: {file_size / 1024 / 1024:.1f} MB")
                                    
                                    # Accept any reasonable file size (>100KB)
                                    if file_size > 100000:
                                        logger.info(f"YouTube video downloaded: {video_file}")
                                        return video_file
                                    else:
                                        logger.warning(f"File too small ({file_size} bytes), trying next format")
                                        continue
                    except Exception as e:
                        error_str = str(e)
                        logger.debug(f"Format {format_spec} failed: {error_str[:150]}")
                        
                        # Log specific errors for diagnostics
                        if "410" in error_str or "unavailable" in error_str.lower():
                            logger.error("Video is unavailable (410 error - likely removed or restricted)")
                        elif "403" in error_str or "access" in error_str.lower():
                            logger.error("Access denied (403 - possibly geo-restricted or age-restricted)")
                        
                        continue
                
                logger.error("All YouTube format attempts exhausted")
                return None
                
            except Exception as e:
                logger.warning(f"YouTube download failed: {e}")
                return None

        # Fallback: Direct HTTP download for direct MP4 links
        logger.info(f"Attempting direct HTTP download from: {url}")
        
        temp_dir = Path(config.temp_upload_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        fname = Path(url).name
        if not fname or "." not in fname or len(fname) > 100:
            fname = f"download_{int(time.time())}.mp4"

        out_path = temp_dir / fname

        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        logger.info(f"Downloaded to: {out_path}")
        return str(out_path)
        
    except Exception as e:
        logger.error(f"Failed to download URL: {e}")
        return None


def extract_audio(video_path: str) -> Optional[str]:
    """Extract audio track from a video file.
    
    Uses moviepy to extract the audio track and save it as an MP3 file.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Path to the extracted audio file, or None on failure
    """
    try:
        from moviepy import VideoFileClip
        from config import config
        
        logger.info(f"Extracting audio from: {video_path}")
        
        # Create output directory
        temp_dir = Path(config.temp_upload_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate output path
        video_stem = Path(video_path).stem
        audio_path = temp_dir / f"{video_stem}_audio.mp3"
        
        # Load video and extract audio
        clip = VideoFileClip(video_path)
        
        if clip.audio is None:
            logger.warning(f"No audio track found in {video_path}")
            return None
        
        # Write audio to MP3 (without verbose parameter for compatibility)
        try:
            clip.audio.write_audiofile(str(audio_path))
        except TypeError:
            # Fallback for older moviepy versions
            clip.audio.write_audiofile(
                str(audio_path),
                verbose=False,
                logger=None
            )
        
        # Clean up
        clip.close()
        
        logger.info(f"Audio extracted to: {audio_path}")
        return str(audio_path)
        
    except ImportError:
        logger.error("MoviePy not installed; cannot extract audio")
        return None
    except Exception as e:
        logger.error(f"Audio extraction failed: {e}")
        return None


def transcribe_audio(audio_path: str) -> Optional[str]:
    """Transcribe audio using OpenAI Whisper.
    
    Uses the whisper library to transcribe audio files to text.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        Transcribed text, or None on failure
    """
    try:
        import whisper
        
        logger.info(f"Transcribing audio: {audio_path}")
        
        # Load the base Whisper model
        model = whisper.load_model("base")
        
        # Transcribe the audio
        result = model.transcribe(audio_path)
        
        transcript = result.get("text", "").strip()
        
        if transcript:
            logger.info(f"Transcription complete: {len(transcript)} characters")
            return transcript
        else:
            logger.warning("Whisper returned empty transcription")
            return None
        
    except ImportError:
        logger.error("Whisper not installed; install with: pip install openai-whisper")
        return None
    except Exception as e:
        logger.error(f"Audio transcription failed: {e}")
        return None


def get_youtube_transcript(url: str) -> Optional[str]:
    """Get transcript directly from YouTube using YouTube Transcript API.
    
    This is more accurate than extracting audio and transcribing with Whisper.
    Only works for YouTube videos with available transcripts.
    
    Args:
        url: YouTube video URL or video ID
        
    Returns:
        Transcript text if available, None otherwise
    """
    try:
        transcript_service = get_transcript_service()
        if not transcript_service.available:
            logger.info("YouTube Transcript API not available, falling back to Whisper")
            return None
        
        transcript = transcript_service.extract(url)
        if transcript:
            logger.info(f"Successfully extracted YouTube transcript ({len(transcript)} chars)")
            return transcript
        
        logger.warning("Could not get YouTube transcript, falling back to Whisper")
        return None
        
    except Exception as e:
        logger.warning(f"YouTube transcript extraction failed: {e}")
        return None


@cached('transcript')
def extract_and_transcribe(video_path: str) -> Optional[str]:
    """Extract audio from video and transcribe it in one step.
    
    Convenience function that handles both audio extraction and transcription.
    Results are cached to avoid re-transcribing the same video.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Transcribed text, or None on failure
    """
    try:
        # Extract audio from video
        audio_path = extract_audio(video_path)
        if not audio_path:
            logger.warning("Failed to extract audio")
            return None
        
        # Transcribe the extracted audio
        transcript = transcribe_audio(audio_path)
        
        # Clean up audio file
        try:
            os.remove(audio_path)
        except Exception as e:
            logger.debug(f"Could not clean up audio file: {e}")
        
        return transcript
        
    except Exception as e:
        logger.error(f"Extract and transcribe failed: {e}")
        return None
