"""Ollama client for AI text generation and responses.

Provides a lightweight wrapper around the Ollama API for generating
responses based on user prompts and conversation history.
"""

import logging
from typing import Dict, List, Optional

import requests

from config import config
from models import AIResponse, ConversationMessage, VideoDetails

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama API."""
    
    def __init__(self, host: str = None, model: str = None, timeout: int = None):
        """Initialize Ollama client.
        
        Args:
            host: Ollama API host (defaults to config)
            model: Model name to use (defaults to config)
            timeout: Request timeout in seconds (defaults to config)
        """
        self.host = host or config.ollama.host
        self.model = model or config.ollama.model
        self.timeout = timeout or config.ollama.timeout
        self.api_endpoint = f"{self.host}/api/generate"
    
    def is_available(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            response = requests.get(
                f"{self.host}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False
    
    def generate_response(
        self,
        user_message: str = None,
        video_path: Optional[str] = None,
        history: Optional[List[ConversationMessage]] = None,
        video_frames: Optional[List[dict]] = None,
        transcript: Optional[str] = None,
        extract_video_details: bool = False,
    ) -> AIResponse:
        """Generate an AI response using Ollama.
        
        Args:
            user_message: The user's prompt/question
            video_path: Path to the video being analyzed (for context)
            history: Conversation history for context
            video_frames: Extracted frames from video with timestamps
            transcript: Transcribed audio from the video
            extract_video_details: If True, extract video metadata from response
            
        Returns:
            AIResponse object with generated text and metadata
        """
        try:
            # Build context from history, frames, and transcript
            context = self._build_context(
                user_message or "",
                video_path,
                history,
                video_frames,
                transcript
            )
            
            # Call Ollama API
            response = requests.post(
                self.api_endpoint,
                json={
                    "model": self.model,
                    "prompt": context,
                    "stream": False,
                },
                timeout=self.timeout,
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama API error: {response.status_code}")
                return AIResponse(
                    text="Error communicating with AI service",
                    error=f"HTTP {response.status_code}"
                )
            
            result = response.json()
            generated_text = result.get("response", "").strip()
            
            # Extract video details if requested (for summaries)
            video_details = None
            if extract_video_details and generated_text:
                video_details = self._extract_video_details_from_response(generated_text)
                logger.debug(f"Extracted video details: {video_details.content_type}")
            
            return AIResponse(
                text=generated_text,
                segments=[],
                metadata={"model": self.model},
                video_details=video_details
            )
            
        except requests.exceptions.Timeout:
            logger.error("Ollama request timed out")
            return AIResponse(
                text="AI service request timed out",
                error="Timeout"
            )
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return AIResponse(
                text="Failed to generate response",
                error=str(e)
            )
    
    def _extract_video_details_from_response(self, response_text: str) -> VideoDetails:
        """Extract video metadata from the AI response summary.
        
        Parses the response to identify:
        - Content type (TV show, movie, tutorial, etc.)
        - Show name, episode number, title
        - Main characters and topics
        - Genres
        
        Args:
            response_text: The AI-generated summary text
            
        Returns:
            VideoDetails object with extracted metadata
        """
        details = VideoDetails()
        
        # Convert to lowercase for case-insensitive matching
        text_lower = response_text.lower()
        
        # Detect content type
        if any(phrase in text_lower for phrase in ["tv show", "episode", "season", "series"]):
            details.content_type = "TV Show"
        elif any(phrase in text_lower for phrase in ["movie", "film"]):
            details.content_type = "Movie"
        elif any(phrase in text_lower for phrase in ["tutorial", "how to", "guide"]):
            details.content_type = "Tutorial"
        elif any(phrase in text_lower for phrase in ["presentation", "conference", "talk"]):
            details.content_type = "Presentation"
        elif any(phrase in text_lower for phrase in ["documentary", "news", "report"]):
            details.content_type = "Documentary"
        elif any(phrase in text_lower for phrase in ["interview"]):
            details.content_type = "Interview"
        else:
            # Try to infer from content
            if "character" in text_lower or "scene" in text_lower:
                details.content_type = "Video Content"
            else:
                details.content_type = "Unknown"
        
        logger.debug(f"Detected content type: {details.content_type}")
        
        return details
    

    def summarize(self, video_path: str, video_frames: Optional[List[dict]] = None, transcript: Optional[str] = None) -> AIResponse:
        """Generate a summary of a video.
        
        Creates a summary based on text extracted from video frames and audio transcript.
        Transcript provides comprehensive content information, frames provide visual context.
        
        Args:
            video_path: Path to the video file
            video_frames: Extracted frames from video with timestamps and descriptions
            transcript: Transcribed audio from the video (optional but highly recommended)
            
        Returns:
            AIResponse with video summary
        """
        # Build a more specific prompt based on what data is available
        if transcript and len(transcript.strip()) > 50:
            prompt = (
                "You are analyzing a video. Use the transcript (PRIORITY) and frame descriptions (CONTEXT) to create a comprehensive summary.\n\n"
                "ANALYSIS TASKS:\n"
                "1. **Identify Content Type**: Is this a TV show episode, movie, tutorial, presentation, etc.?\n"
                "2. **For TV Shows specifically**: Extract the show name, season/episode if visible, main characters involved, and plot summary\n"
                "3. **Extract Key Points**: What are the main topics, events, or information discussed?\n"
                "4. **Note Visual Elements**: Any on-screen text, graphics, or important visual indicators\n"
                "5. **Determine Purpose**: What is the intended goal or message of this video?\n\n"
                "INSTRUCTIONS:\n"
                "- PRIORITY 1: Extract information from the TRANSCRIPT (most accurate)\n"
                "- PRIORITY 2: Use frame descriptions to confirm or add visual context\n"
                "- PRIORITY 3: Identify any opening/closing credits, logos, or show identifiers\n"
                "- Output: Be specific and fact-based. Include show/episode name if detectable from transcript.\n"
                "- Format: 2-4 clear, informative sentences covering the main content.\n\n"
                "SPECIAL FOCUS: If this is a TV show, identify the show name and episode content. If this is other content, describe it accurately."
            )
        else:
            prompt = (
                "Analyze the key frames extracted from this video to create a summary.\n\n"
                "ANALYSIS TASKS:\n"
                "1. **Content Type**: What type of video is this? (TV show, movie, tutorial, etc.)\n"
                "2. **For TV Shows**: Look for show logos, opening sequences, character identification, or on-screen text\n"
                "3. **Visual Content**: What do the frames show? Identify any text, graphics, or important visual elements\n"
                "4. **Scene Description**: What appears to be happening in the video based on the visual frames?\n\n"
                "INSTRUCTIONS:\n"
                "- Use all available frame descriptions and text recognition results\n"
                "- Be specific about identified content (show names, characters, locations if visible)\n"
                "- Note if frames contain opening/closing credits or title sequences\n"
                "- Output: 2-4 sentences based on careful visual analysis\n\n"
                "SPECIAL FOCUS: If TV show elements are visible, identify them. Otherwise describe the video content accurately."
            )
        
        return self.generate_response(
            prompt,
            video_path=video_path,
            video_frames=video_frames,
            transcript=transcript,
            extract_video_details=True  # Extract metadata for summaries
        )
    
    def generate_summary(self, video_frames: Optional[List[dict]] = None, transcript: Optional[str] = None) -> AIResponse:
        """Generate a comprehensive summary from frames and transcript.
        
        High-level method for generating video summaries when both visual and audio
        content are available.
        
        Args:
            video_frames: Extracted frames from video with timestamps and descriptions
            transcript: Transcribed audio from the video
            
        Returns:
            AIResponse with comprehensive video summary
        """
        prompt = (
            "Analyze the video content provided and create a clear, comprehensive summary. "
            "Your summary should:\n"
            "1. Identify the main topic and key themes\n"
            "2. Highlight the most important points or takeaways\n"
            "3. Describe the purpose or type of video (tutorial, presentation, demo, etc.)\n"
            "4. Note any specific information, statistics, or conclusions mentioned\n\n"
            "Keep the summary concise (2-4 sentences) but informative."
        )
        
        return self.generate_response(
            prompt,
            video_frames=video_frames,
            transcript=transcript
        )
    
    def answer_question(
        self,
        question: str,
        video_frames: Optional[List[dict]] = None,
        transcript: Optional[str] = None,
        chat_history: Optional[List[ConversationMessage]] = None,
        video_details: Optional[VideoDetails] = None,
    ) -> AIResponse:
        """Answer a user question about the video using frames and transcript.
        
        Provides context-aware answers by combining:
        - The user's current question
        - Extracted video frames and visual analysis
        - Transcribed audio content
        - Previous conversation history for context
        - Known video details (type, title, show name, etc.)
        
        Args:
            question: The user's question about the video
            video_frames: Extracted frames from video with timestamps and descriptions
            transcript: Transcribed audio from the video
            chat_history: Previous conversation messages for context
            video_details: VideoDetails object with identified metadata about the video
            
        Returns:
            AIResponse with answer to the user's question
        """
        # Build context-aware prompt based on video details
        prompt_parts = [
            "Answer the user's question accurately and specifically based on the video content."
        ]
        
        # Add video context if available
        if video_details:
            prompt_parts.append(f"\nYou are analyzing a {video_details.content_type if video_details.content_type else 'video'}.")
            
            if video_details.show_name:
                prompt_parts.append(f"Show: {video_details.show_name}")
                if video_details.episode_number:
                    prompt_parts.append(f"Episode: {video_details.episode_number}")
            
            if video_details.characters:
                prompt_parts.append(f"Main characters: {', '.join(video_details.characters)}")
            
            if video_details.key_topics:
                prompt_parts.append(f"Key topics: {', '.join(video_details.key_topics)}")
        
        prompt_parts.extend([
            "\nInstructions:",
            "- Cite specific moments, timestamps, or quotes from the video when answering",
            "- Use information from the transcript (most accurate) as primary source",
            "- Use visual frame descriptions as secondary context",
            "- Be accurate and specific - avoid speculation",
            "- If the video doesn't contain the answer, say so clearly",
        ])
        
        prompt = "\n".join(prompt_parts)
        
        return self.generate_response(
            user_message=prompt,
            history=chat_history,
            video_frames=video_frames,
            transcript=transcript,
        )
    
    def _build_context(
        self,
        user_message: str,
        video_path: Optional[str] = None,
        history: Optional[List[ConversationMessage]] = None,
        video_frames: Optional[List[dict]] = None,
        transcript: Optional[str] = None,
    ) -> str:
        """Build the full prompt context from history, frames, and transcript.
        
        Args:
            user_message: Current user message
            video_path: Path to video being analyzed
            history: Conversation history
            video_frames: Extracted frames with timestamps and descriptions
            transcript: Transcribed audio content from the video
            
        Returns:
            Full prompt string for Ollama
        """
        parts = [
            "You are analyzing a video based on extracted content.",
            "You have access to the following information sources:",
            "1. TRANSCRIPT: Audio transcription (most accurate for content)"
            if transcript and len(transcript.strip()) > 0
            else "1. TRANSCRIPT: Not available for this video",
            "2. FRAMES: Visual descriptions of key frames from the video",
            "",
            "Instructions:",
            "- Prioritize transcript information when available (it's most accurate)",
            "- Use frame descriptions for visual context and confirmation",
            "- Be specific and fact-based, avoiding generic statements",
            "- Focus on the actual content, not speculation"
        ]
        
        # Add transcript FIRST and prominently if available (most important content signal)
        if transcript and len(transcript.strip()) > 20:
            parts.append("")
            parts.append("=" * 80)
            parts.append("📝 VIDEO TRANSCRIPT (Audio Content)")
            parts.append("=" * 80)
            
            # Include more of the transcript for better context
            transcript_preview = transcript[:3000]
            parts.append(transcript_preview)
            
            if len(transcript) > 3000:
                parts.append(f"\n[... additional {len(transcript) - 3000} characters of transcript ...]")
            
            parts.append("=" * 80)
        else:
            parts.append("")
            parts.append("=" * 80)
            parts.append("⚠️  No transcript available - Analysis will be based on visual frames only")
            parts.append("=" * 80)
        
        # Add frame descriptions with better formatting
        if video_frames and len(video_frames) > 0:
            parts.append("")
            parts.append("=" * 80)
            parts.append(f"📸 KEY FRAMES ({len(video_frames)} frames analyzed)")
            parts.append("=" * 80)
            
            for i, frame in enumerate(video_frames, 1):
                timestamp = frame.get('timestamp', '??:??')
                description = frame.get('description', 'Frame')
                parts.append(f"\n[{timestamp}] Frame {i}:")
                parts.append(f"  {description}")
            
            parts.append("")
            parts.append("=" * 80)
        
        # Add conversation history if present
        if history and len(history) > 1:
            parts.append("\n💬 RECENT CONVERSATION:")
            for msg in history[-4:]:
                role = "User" if msg.role == "user" else "Assistant"
                text = msg.text[:150]
                parts.append(f"\n{role}: {text}")
        
        # Add the question/instruction
        if user_message:
            parts.append("\n" + "=" * 80)
            parts.append("TASK: " + user_message)
            parts.append("=" * 80)
        
        return "\n".join(parts)


# Singleton instance
_ollama_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Get or create the singleton Ollama client."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client
