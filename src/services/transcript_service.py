"""YouTube transcript extraction service.

Provides methods to extract video transcripts directly from YouTube,
which is more accurate than frame-based analysis when available.
"""

import logging
import re
from typing import Optional

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_TRANSCRIPT_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPT_AVAILABLE = False

logger = logging.getLogger(__name__)


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats.
    
    Args:
        url: YouTube video URL (supports various formats)
        
    Returns:
        Video ID if found, None otherwise
    """
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:youtube\.com\/embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtube\.com\/v\/)([0-9A-Za-z_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # Check if URL is already a video ID
    if re.match(r'^[0-9A-Za-z_-]{11}$', url):
        return url
    
    return None


def get_youtube_transcript(url: str, languages: Optional[list] = None) -> Optional[str]:
    """Extract transcript from YouTube video.
    
    Attempts to get the video transcript directly from YouTube's API.
    Falls back to requesting transcripts in different languages if specified.
    
    Args:
        url: YouTube video URL or video ID
        languages: List of language codes to try (e.g., ['en', 'en-US'])
                   Default: ['en'] if not specified
        
    Returns:
        Full transcript text if successful, None if unavailable or API not installed
    """
    if not YOUTUBE_TRANSCRIPT_AVAILABLE:
        logger.warning("youtube-transcript-api not installed. Install with: pip install youtube-transcript-api")
        return None
    
    video_id = extract_video_id(url)
    if not video_id:
        logger.error(f"Could not extract video ID from URL: {url}")
        return None
    
    if languages is None:
        languages = ['en']
    
    try:
        # Try to get transcript in requested languages
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        except Exception:
            # Fallback: try auto-generated transcripts
            logger.info(f"Manual transcript not available, trying auto-generated for video {video_id}")
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Combine all transcript entries into single text
        full_transcript = ' '.join([entry['text'] for entry in transcript_list])
        
        logger.info(f"Successfully extracted transcript for video {video_id} ({len(full_transcript)} chars)")
        return full_transcript
        
    except Exception as e:
        logger.warning(f"Failed to get transcript for {video_id}: {e}")
        return None


def get_available_transcripts(url: str) -> Optional[dict]:
    """Get list of available transcripts for a video.
    
    Useful for checking what languages are available before extracting.
    
    Args:
        url: YouTube video URL or video ID
        
    Returns:
        Dict with 'manually_created_transcripts' and 'generated_transcripts' keys
        Returns None if unavailable
    """
    if not YOUTUBE_TRANSCRIPT_AVAILABLE:
        return None
    
    video_id = extract_video_id(url)
    if not video_id:
        return None
    
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        return {
            'manually_created': [t.language for t in transcript_list.manually_created_transcripts],
            'auto_generated': [t.language for t in transcript_list.generated_transcripts],
        }
    except Exception as e:
        logger.warning(f"Could not list transcripts for {video_id}: {e}")
        return None


# Singleton instance
_instance = None


def get_transcript_service():
    """Get singleton instance of transcript service."""
    global _instance
    if _instance is None:
        _instance = TranscriptService()
    return _instance


class TranscriptService:
    """Service for extracting YouTube transcripts."""
    
    def __init__(self):
        """Initialize transcript service."""
        self.available = YOUTUBE_TRANSCRIPT_AVAILABLE
        if not self.available:
            logger.warning("YouTube Transcript API not available. Install: pip install youtube-transcript-api")
    
    def extract(self, url: str, languages: Optional[list] = None) -> Optional[str]:
        """Extract transcript from YouTube video.
        
        Args:
            url: YouTube video URL or video ID
            languages: Language codes to try
            
        Returns:
            Transcript text or None
        """
        if not self.available:
            return None
        return get_youtube_transcript(url, languages)
    
    def list_available(self, url: str) -> Optional[dict]:
        """List available transcripts for video.
        
        Args:
            url: YouTube video URL or video ID
            
        Returns:
            Dict of available transcripts or None
        """
        if not self.available:
            return None
        return get_available_transcripts(url)
