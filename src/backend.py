"""Backend service layer for Video Brain.

Coordinates between the Streamlit UI and AI/processing services.
"""

import logging
from typing import Optional

from services.ollama_client import get_ollama_client
from services.session_manager import get_session_manager
from services.video_processor import VideoProcessor
from services.frame_extractor import get_frame_extractor
from utils.storage import extract_and_transcribe, get_youtube_transcript
from models import AIResponse, VideoDetails

logger = logging.getLogger(__name__)


def process_video_upload(video_path: str) -> Optional[dict]:
    """Extract and return video metadata.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Dict with video metadata (duration, fps, etc.) or None on failure
    """
    processor = VideoProcessor()
    metadata = processor.extract_metadata(video_path)
    
    if not metadata:
        logger.warning(f"Could not extract metadata from {video_path}")
        return None
    
    return {
        "duration": metadata.duration,
        "fps": metadata.fps,
        "width": metadata.width,
        "height": metadata.height,
    }


def handle_user_message(
    session_id: str,
    message: str,
    video_path: Optional[str] = None,
    transcript: Optional[str] = None,
    video_details=None,
) -> dict:
    """Process a user message and generate an AI response.
    
    Coordinates:
    - Session history management
    - Video frame extraction for context
    - Transcript context if available
    - Video details (show name, episode, etc) for context
    - AI response generation
    - Error handling and logging
    
    Args:
        session_id: Unique session identifier
        message: User's message/question
        video_path: Path to video being analyzed (optional)
        transcript: Transcribed audio from video (optional)
        video_details: VideoDetails object with identified metadata (optional)
        
    Returns:
        Response dict with 'text', 'segments', and optional 'error' keys
    """
    try:
        # Get or create session
        session_mgr = get_session_manager()
        session_mgr.add_user_message(session_id, message)
        
        # Get conversation history for context
        history = session_mgr.get_recent_history(session_id, max_messages=10)
        
        # Extract video frames if video is provided
        video_frames = None
        if video_path:
            try:
                frame_extractor = get_frame_extractor(num_frames=5)
                frames_data = frame_extractor.extract_frame_descriptions(video_path)
                if frames_data:
                    video_frames = frames_data
                    logger.info(f"Extracted {len(frames_data)} frames from video")
            except Exception as e:
                logger.warning(f"Frame extraction failed: {e}")
        
        # Convert video_details dict to VideoDetails object if needed
        video_details_obj = None
        if video_details:
            if isinstance(video_details, dict):
                # Reconstruct VideoDetails from dict
                video_details_obj = VideoDetails(
                    content_type=video_details.get("content_type"),
                    title=video_details.get("title"),
                    show_name=video_details.get("show_name"),
                    season_number=video_details.get("season_number"),
                    episode_number=video_details.get("episode_number"),
                    episode_title=video_details.get("episode_title"),
                    characters=video_details.get("characters", []),
                    key_topics=video_details.get("key_topics", []),
                    genres=video_details.get("genres", []),
                    duration_seconds=video_details.get("duration_seconds"),
                )
            else:
                video_details_obj = video_details
        
        # Generate response using Ollama with frames and transcript
        ollama = get_ollama_client()
        response = ollama.answer_question(
            message,
            video_frames=video_frames,
            transcript=transcript,
            chat_history=history,
            video_details=video_details_obj,
        )
        
        # Store response in session
        session_mgr.add_assistant_message(session_id, response)
        
        return {
            "text": response.text,
            "segments": response.segments,
            "error": response.error,
        }
        
    except Exception as e:
        logger.error(f"Failed to handle user message: {e}")
        return {
            "text": "Sorry, I encountered an error processing your request.",
            "segments": [],
            "error": str(e),
        }


def summarize_video(session_id: str, video_path: str, transcript: Optional[str] = None) -> dict:
    """Generate a summary of a video.
    
    Extracts key frames and uses transcript (if available) to provide
    comprehensive context for the AI summary generation.
    
    Args:
        session_id: Unique session identifier
        video_path: Path to the video file
        transcript: Transcribed audio from video (optional)
        
    Returns:
        Response dict with summary text and optional error
    """
    try:
        # Get or create session
        session_mgr = get_session_manager()
        
        # Extract video frames for context
        video_frames = None
        try:
            frame_extractor = get_frame_extractor(num_frames=5)
            frames_data = frame_extractor.extract_frame_descriptions(video_path)
            if frames_data:
                video_frames = frames_data
                logger.info(f"Extracted {len(frames_data)} frames for summary")
        except Exception as e:
            logger.warning(f"Frame extraction for summary failed: {e}")
        
        # Generate summary using Ollama with frame and transcript context
        ollama = get_ollama_client()
        response = ollama.summarize(video_path, video_frames=video_frames, transcript=transcript)
        
        # Store in session
        session_mgr.add_assistant_message(session_id, response)
        
        return {
            "text": response.text,
            "segments": response.segments,
            "error": response.error,
            "video_details": response.video_details.to_dict() if response.video_details else None,
        }
        
    except Exception as e:
        logger.error(f"Failed to summarize video: {e}")
        return {
            "text": "",
            "segments": [],
            "error": str(e),
        }
    except Exception as e:
        logger.error(f"Failed to summarize video: {e}")
        return {
            "text": "",
            "segments": [],
            "error": str(e),
        }


def is_ollama_available() -> bool:
    """Check if Ollama service is available.
    
    Returns:
        True if Ollama is reachable, False otherwise
    """
    ollama = get_ollama_client()
    return ollama.is_available()


def get_ollama_status() -> dict:
    """Get detailed Ollama status information.
    
    Returns:
        Dict with availability and model information
    """
    from config import config
    ollama = get_ollama_client()
    
    return {
        "available": ollama.is_available(),
        "host": config.ollama.host,
        "model": config.ollama.model,
        "timeout": config.ollama.timeout,
    }


def extract_transcript(video_path: str) -> Optional[str]:
    """Extract transcript from a video file.
    
    For YouTube URLs, attempts to get the transcript directly from YouTube's
    Transcript API (most accurate). Falls back to Whisper audio transcription
    for local files or when YouTube transcript is unavailable.
    
    Args:
        video_path: Path to video file or YouTube URL
        
    Returns:
        Transcribed text, or None on failure
    """
    try:
        # Check if this is a YouTube URL
        if 'youtube.com' in video_path or 'youtu.be' in video_path:
            logger.info(f"Attempting YouTube transcript API for: {video_path}")
            yt_transcript = get_youtube_transcript(video_path)
            if yt_transcript:
                logger.info(f"YouTube transcript retrieved: {len(yt_transcript)} characters")
                return yt_transcript
            logger.info("YouTube transcript unavailable, falling back to Whisper")
        
        # Fall back to Whisper transcription for local files or failed YouTube
        logger.info(f"Starting Whisper transcription for: {video_path}")
        transcript = extract_and_transcribe(video_path)
        
        if transcript:
            logger.info(f"Whisper transcription complete: {len(transcript)} characters")
            return transcript
        else:
            logger.warning("Transcription returned empty result")
            return None
            
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return None
