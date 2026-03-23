"""Video processing utilities.

Provides lightweight video metadata extraction and processing.
"""

import logging
from typing import Optional

from models import VideoMetadata

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Handles video file processing and metadata extraction."""
    
    @staticmethod
    def extract_metadata(video_path: str) -> Optional[VideoMetadata]:
        """Extract metadata from a video file.
        
        Returns basic properties like duration and fps. Keeping processing
        minimal to avoid heavy transcoding in the Streamlit process.
        
        Args:
            video_path: Path to video file
            
        Returns:
            VideoMetadata object on success, None on failure
        """
        try:
            from moviepy.editor import VideoFileClip
            
            clip = VideoFileClip(video_path)
            duration = clip.duration
            fps = clip.fps
            
            # Try to get dimensions
            width = clip.w if hasattr(clip, 'w') else None
            height = clip.h if hasattr(clip, 'h') else None
            
            # Clean up resources
            try:
                clip.reader.close()
            except Exception:
                pass
            clip.audio = None
            
            return VideoMetadata(
                duration=duration,
                fps=fps,
                width=width,
                height=height
            )
            
        except ImportError:
            logger.warning("moviepy not installed; skipping metadata extraction")
            return None
        except Exception as e:
            logger.error(f"Failed to extract video metadata: {e}")
            return None
    
    @staticmethod
    def validate_video_file(video_path: str) -> bool:
        """Check if a file is a valid video.
        
        Args:
            video_path: Path to video file
            
        Returns:
            True if file appears to be a valid video
        """
        try:
            import os
            if not os.path.exists(video_path):
                return False
            
            # Check file size (most files should be > 1MB)
            if os.path.getsize(video_path) < 1024 * 1024:
                logger.warning(f"Video file suspiciously small: {video_path}")
            
            # Try to get metadata as validation
            metadata = VideoProcessor.extract_metadata(video_path)
            return metadata is not None
            
        except Exception as e:
            logger.error(f"Video validation failed: {e}")
            return False


# Singleton instance
_video_processor: Optional[VideoProcessor] = None


def get_video_processor() -> VideoProcessor:
    """Get the singleton video processor."""
    global _video_processor
    if _video_processor is None:
        _video_processor = VideoProcessor()
    return _video_processor
