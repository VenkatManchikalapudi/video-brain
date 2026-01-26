"""Streamlit frontend for Video Brain.

This module implements a minimal UI that:
- accepts an MP4 upload,
- displays the video inline,
- provides a text input for user prompts/questions,
- shows a running conversation where AI responses may include
  timestamped segments.

The app is intentionally lightweight: heavy processing should be
delegated to background workers or remote services in production.
"""

import streamlit as st
from pathlib import Path
import time
import shutil

from storage import save_temp_file, save_from_url
import backend
import gemini_client


def main():
    """Render the Streamlit UI and handle user interactions.

    Session state keys used:
    - `history`: list of conversation dicts with `user` and `ai` keys.
    - `session_id`: simple identifier for the session used by backend.
    """
    st.set_page_config(page_title="Video Brain", layout="wide")
    st.title("Video Brain")

    # Check for ffmpeg availability. Prefer system `ffmpeg`, fall back to
    # the `imageio-ffmpeg` package if installed. Show a visible warning
    # so the developer/user can install the missing dependency.
    ffmpeg_available = shutil.which("ffmpeg") is not None
    if not ffmpeg_available:
        try:
            import imageio_ffmpeg  # type: ignore

            ffmpeg_available = True
        except Exception:
            ffmpeg_available = False

    if not ffmpeg_available:
        st.warning(
            "FFmpeg not found. Install system ffmpeg (e.g. `brew install ffmpeg`) "
            "or install the Python package `imageio-ffmpeg` (pip install imageio-ffmpeg). "
            "Video preview and processing may be limited until FFmpeg is available."
        )

    # Show Gemini availability status prominently so users know whether
    # model calls will hit the real Gemini service or fall back to the
    # local mock behavior.
    if not gemini_client.is_gemini_available():
        st.warning(
            "Google Gemini is not available — GEMINI_API_KEY missing or client not installed. "
            "AI responses will be mocked until Gemini is configured."
        )
    else:
        st.info("Google Gemini appears configured — model calls will use Gemini.")

    # Initialize conversation history in Streamlit session state.
    if "history" not in st.session_state:
        st.session_state.history = []

    # Three-column layout: upload | preview | questions
    col1, col2, col3 = st.columns([1, 2, 1])

    # Column 1: drag & drop upload area (Streamlit's file_uploader supports drag/drop)
    with col1:
        st.markdown("### Upload")
        uploaded = st.file_uploader("Drop MP4 here", type=["mp4"], key="uploader")

        # Also accept a public video URL; the user can either stream the
        # URL directly or download it for backend processing.
        video_url = st.text_input("Or paste a public MP4 URL:", key="video_url")
        fetch_url = st.button("Fetch URL")

        if uploaded is not None:
            # Save uploaded file and store path in session state for later use.
            video_path = save_temp_file(uploaded)
            st.session_state.video_path = video_path
            st.success("Uploaded and saved")

            # Create or reuse a session id and request a summary for the uploaded video.
            session_id = st.session_state.get("session_id") or str(int(time.time()))
            st.session_state.session_id = session_id
            summary = backend.summarize_video(session_id, video_path)
            st.session_state.summary = summary.get("text")

        if fetch_url and video_url:
            # Use `save_from_url` which will try to resolve a direct media
            # stream URL (via yt-dlp for YouTube) or download a direct MP4.
            fetched = save_from_url(video_url)
            if fetched:
                # `fetched` may be a local path or a direct media URL.
                st.session_state.video_path = fetched
                st.success("Video source resolved and saved for processing")

                # Request a summary automatically when a URL is resolved.
                session_id = st.session_state.get("session_id") or str(int(time.time()))
                st.session_state.session_id = session_id
                summary = backend.summarize_video(session_id, fetched)
                # Save and surface any error returned by the model call.
                st.session_state.summary = summary.get("text")
                if summary.get("error"):
                    st.error("Gemini error: see logs for details")
            else:
                st.session_state.video_path = None
                st.error("Could not fetch or resolve the provided URL.")

    # Column 2: video preview and simple metadata
    with col2:
        st.markdown("### Preview")
        video_to_show = None
        # Prefer the latest uploaded file saved in session state.
        if "video_path" in st.session_state:
            video_to_show = st.session_state.video_path
        # Preview logic:
        # - If the user provided a YouTube/page URL, Streamlit can embed the
        #   page URL for a nice player experience. If `uploaded` is set, show
        #   that directly. If we resolved a direct media URL (HTTP) or local
        #   path in `video_to_show`, try streaming it via `st.video`.
        if uploaded is not None:
            st.video(uploaded)
        elif video_to_show:
            # If `video_to_show` looks like a web page (YouTube), still show
            # the original `video_url` for a good embed experience when
            # available in session state.
            try:
                if isinstance(video_to_show, str) and (video_to_show.startswith("http://") or video_to_show.startswith("https://")):
                    # If the user originally entered a page URL, embed it.
                    # Otherwise `st.video` can accept direct media stream URLs.
                    st.video(video_to_show)
                else:
                    with open(video_to_show, "rb") as f:
                        st.video(f.read())
            except Exception:
                st.warning("Could not preview the saved video file.")

        # Show lightweight metadata if available.
        if "video_path" in st.session_state:
            meta = backend.process_video_upload(st.session_state.video_path)
            if meta:
                st.info(f"Video metadata: {meta}")

        # Display generated summary (if any).
        if "summary" in st.session_state and st.session_state.summary:
            st.markdown("### Summary")
            st.markdown(st.session_state.summary)

    # Column 3: questions / prompt input
    with col3:
        st.markdown("### Ask")
        user_input = st.text_input("Ask about the video or enter a prompt:", key="prompt")
        send = st.button("Send")

        if send and user_input:
            # Create or reuse a simple session id for conversation context.
            session_id = st.session_state.get("session_id") or str(int(time.time()))
            st.session_state.session_id = session_id

            # Pass the current video path (if any) to the backend for context.
            video_path_arg = st.session_state.get("video_path")
            response = backend.handle_user_message(session_id, user_input, video_path=video_path_arg)

            # Append to the local display history.
            st.session_state.history.append({"user": user_input, "ai": response})
            if response.get("error"):
                st.error("Gemini error: see logs for details")

    # Render conversation history. Keep rendering simple and readable.
    st.subheader("Conversation")
    for item in st.session_state.history:
        st.markdown(f"**You:** {item['user']}")
        ai = item["ai"] or {}
        st.markdown(f"**AI:** {ai.get('text')}")

        # If the AI returned timestamped segments, show them as bullets.
        segments = ai.get("segments") or []
        for s in segments:
            st.markdown(f"- `{s.get('time')}`: {s.get('text')}")


if __name__ == "__main__":
    main()
