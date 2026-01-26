"""Backend helpers for Video Brain.

This module provides lightweight video metadata extraction and a small
in-memory session history used by the Streamlit frontend. It delegates
text-generation to `gemini_client.generate_response`, which may call
Google Gemini or return a local mock for development.

Notes:
- `_SESSIONS` is an in-memory store mapping `session_id` -> list of
  message dicts. For production use a database or external cache.
"""

import os
from typing import Dict, List
import gemini_client


# Simple in-memory session store. For production, replace with persistent store.
_SESSIONS: Dict[str, List[Dict]] = {}


def process_video_upload(video_path: str) -> Dict:
    """Extract lightweight metadata from an uploaded video file.

    Returns a dict with keys like `duration` and `fps` on success.
    On failure returns an empty dict. This function intentionally keeps
    processing minimal (no heavy transcoding) so it is safe to run in
    the Streamlit process.
    """
    try:
        # Import moviepy lazily so the module can still be imported even
        # if moviepy isn't installed. This avoids hard failures at
        # application startup and allows graceful degradation.
        from moviepy.editor import VideoFileClip

        # Load clip to inspect basic properties (duration, fps).
        clip = VideoFileClip(video_path)
        duration = clip.duration
        fps = clip.fps

        # Close the reader and release resources. We avoid keeping audio
        # references around to prevent file locks or memory retention.
        try:
            clip.reader.close()
        except Exception:
            # Reader close may not always be available; ignore safely.
            pass
        clip.audio = None

        return {"duration": duration, "fps": fps}
    except ImportError:
        # moviepy is not installed — return empty metadata and allow the
        # application to continue running. Recommend installing moviepy
        # and ffmpeg for full functionality.
        return {}
    except Exception:
        # Return an empty dict on any other failure — callers should handle this.
        return {}


def handle_user_message(session_id: str, message: str, video_path: str = None) -> Dict:
    """Record a user message in the session and fetch AI response.

    - Ensures a session history list exists for `session_id`.
    - Appends the user's message to the session history.
    - Calls `gemini_client.generate_response` with the video path,
      user message and conversation history; this function is expected
      to return a dict with at least the key `text` and optional
      `segments` (timestamped notes).
    - Appends the assistant's reply text to the session history and
      returns the full AI response dict to the caller.

    For production you may want to:
    - Persist session history to a database, and
    - Add request/response logging and error handling.
    """
    if session_id not in _SESSIONS:
        # Initialize an empty conversation history for this session.
        _SESSIONS[session_id] = []

    # Save the incoming user message in session history.
    _SESSIONS[session_id].append({"role": "user", "text": message})
    history = _SESSIONS[session_id]

    # Query the Gemini client (or mock) for an AI response.
    ai_resp = gemini_client.generate_response(video_path, message, history)

    # Store assistant response text back into session history for later
    # dialog context. We only store the textual part here for simplicity.
    _SESSIONS[session_id].append({"role": "assistant", "text": ai_resp.get("text")})

    return ai_resp


def summarize_video(session_id: str, video_path: str) -> Dict:
    """Generate a concise summary for the provided video.

    - Ensures session exists for context.
    - Calls the Gemini client with a summarization prompt and stores the
      assistant reply in session history.
    Returns the AI response dict (with `text` and optional `segments`).
    """
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = []

    # Add a system-like user intent for summarization to the history.
    prompt = (
        "Summarize the video concisely in 3-5 bullet points, "
        "including key events, people mentioned, and notable timestamps (MM:SS)."
    )

    _SESSIONS[session_id].append({"role": "user", "text": f"SUMMARY_REQUEST: {prompt}"})
    history = _SESSIONS[session_id]

    ai_resp = gemini_client.generate_response(video_path, prompt, history)

    _SESSIONS[session_id].append({"role": "assistant", "text": ai_resp.get("text")})
    return ai_resp
