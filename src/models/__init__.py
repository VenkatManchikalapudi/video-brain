"""Data models and schemas for Video Brain."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class TextSegment:
    """A timestamped text segment from video analysis."""
    
    time: str  # Format: MM:SS
    text: str


@dataclass
class AIResponse:
    """Response structure from the AI service."""
    
    text: str
    segments: List[TextSegment] = field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    video_details: Optional['VideoDetails'] = None  # Video content details extracted from analysis


@dataclass
class ConversationMessage:
    """A single message in a conversation."""
    
    role: str  # "user" or "assistant"
    text: str
    timestamp: Optional[float] = None


@dataclass
class VideoMetadata:
    """Metadata extracted from a video file."""
    
    duration: float
    fps: float
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class VideoDetails:
    """Content details extracted from video analysis."""
    
    content_type: Optional[str] = None  # "TV show", "Movie", "Tutorial", etc.
    title: Optional[str] = None  # Video/movie/episode title
    show_name: Optional[str] = None  # For TV shows: the series name
    season_number: Optional[int] = None  # For TV shows
    episode_number: Optional[int] = None  # For TV shows
    episode_title: Optional[str] = None  # For TV shows
    characters: List[str] = field(default_factory=list)  # Main characters involved
    key_topics: List[str] = field(default_factory=list)  # Main topics discussed
    genres: List[str] = field(default_factory=list)  # Video genres/categories
    duration_seconds: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "content_type": self.content_type,
            "title": self.title,
            "show_name": self.show_name,
            "season_number": self.season_number,
            "episode_number": self.episode_number,
            "episode_title": self.episode_title,
            "characters": self.characters,
            "key_topics": self.key_topics,
            "genres": self.genres,
            "duration_seconds": self.duration_seconds,
        }
