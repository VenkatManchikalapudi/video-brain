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

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import time
import shutil

from utils.storage import save_temp_file, save_from_url
from utils.cache import get_cache
from utils.logging_config import setup_logging
import backend
from services.frame_extractor import get_frame_extractor

# Initialize logging once at startup
setup_logging(level="INFO")


def main():
    """Render the Streamlit UI and handle user interactions.

    Session state keys used:
    - `history`: list of chat messages for Q&A
    - `session_id`: simple identifier for the session used by backend
    - `video_path`: path to the current video
    - `transcript`: transcribed audio from the video
    - `frames_data`: extracted key frames with descriptions
    """
    st.set_page_config(page_title="Video Brain", layout="wide")
    st.title("🧠 Video Brain")
    st.markdown("*Understand videos using local AI - frames, text recognition, and audio transcription*")

    # Check for ffmpeg availability
    ffmpeg_available = shutil.which("ffmpeg") is not None
    if not ffmpeg_available:
        try:
            import imageio_ffmpeg
            ffmpeg_available = True
        except Exception:
            ffmpeg_available = False

    if not ffmpeg_available:
        st.error(
            "❌ **FFmpeg not installed** - Required for audio transcription\n\n"
            "Install with:\n"
            "- **macOS**: `brew install ffmpeg`\n"
            "- **Linux**: `apt install ffmpeg` or `dnf install ffmpeg`\n"
            "- **Windows**: `choco install ffmpeg` or download from ffmpeg.org\n\n"
            "Without FFmpeg, video summaries will be based on visual analysis only (less accurate)."
        )

    # Show Ollama availability status
    if not backend.is_ollama_available():
        st.error(
            "❌ Ollama is not available. Ensure Ollama is running: `ollama serve` "
            "(Install: https://ollama.ai)"
        )
    else:
        st.success("✅ Ollama is available - using local LLM for responses")
    
    # Sidebar: Settings and utilities
    with st.sidebar:
        st.markdown("### ⚙️ Settings & Tools")
        
        # Cache management
        st.markdown("**Cache Management**")
        cache = get_cache()
        col_cache1, col_cache2 = st.columns([2, 1])
        with col_cache1:
            st.text(f"Cache status: Active")
        with col_cache2:
            if st.button("Clear", key="clear_cache"):
                count = cache.clear()
                st.success(f"Cleared {count} cache files")
                st.rerun()
        
        st.markdown("---")
        st.markdown("**Processing Info**")
        st.caption("The app caches transcripts and frames to avoid reprocessing. Clear cache to force reprocessing.")
        
        st.markdown("---")
        st.markdown("**🆘 Troubleshooting**")
        with st.expander("YouTube download not working?"):
            st.markdown("""
            **Common issues:**
            - Some videos use HLS-only streaming (not downloadable)
            - Age-restricted content needs special handling
            - Geographic restrictions may apply
            - YouTube frequently changes formats
            
            **Solution:**
            Download videos locally using a tool like:
            - [yt-dlp](https://github.com/yt-dlp/yt-dlp)
            - [4K Video Downloader](https://www.4kdownload.com/)
            - Others...
            
            Then upload the MP4 using the **Local File** tab.
            """)
        
        with st.expander("Summary is inaccurate?"):
            st.markdown("""
            **Why this might happen:**
            - Audio quality affects transcription accuracy
            - Complex content needs more frames
            - Some videos have background noise
            
            **Try:**
            1. Expand **Debug Info** below summary to see what was extracted
            2. Check transcript preview - is it accurate?
            3. Clear cache and reprocess
            4. Try uploading a higher-quality version
            """)
        
        with st.expander("Performance slow?"):
            st.markdown("""
            **First time processing:**
            - Frame extraction: ~2-5 seconds
            - Transcription: ~30-60 seconds
            - Summary: ~3-5 seconds
            - Total: ~45-75 seconds
            
            **Repeated processing:**
            - Uses cache (instant)
            - Click "Clear" cache to reprocess
            
            **Speed up:**
            Use shorter videos or upload MP4s
            (YouTube downloads take longer)
            """)

    # Initialize session state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "transcript" not in st.session_state:
        st.session_state.transcript = None
    if "frames_data" not in st.session_state:
        st.session_state.frames_data = None
    if "video_details" not in st.session_state:
        st.session_state.video_details = None
    if "video_processed" not in st.session_state:
        st.session_state.video_processed = False

    # Three-column layout
    col1, col2, col3 = st.columns([1, 2, 1])

    # Column 1: Upload
    with col1:
        st.markdown("### 📤 Upload Video")
        
        # Tab 1: Local File Upload
        upload_tabs = st.tabs(["📁 Local File", "🎥 YouTube URL", "🔗 Other URL"])
        
        with upload_tabs[0]:
            uploaded = st.file_uploader("Drop MP4 here", type=["mp4"], key="uploader")
            if uploaded is not None:
                video_path = save_temp_file(uploaded)
                st.session_state.video_path = video_path
                st.session_state.video_processed = False  # Reset processing flag
                st.success("✅ Uploaded and saved")
        
        # Tab 2: YouTube URL
        with upload_tabs[1]:
            st.markdown("**Enter a YouTube video URL:**")
            youtube_url = st.text_input(
                "YouTube URL",
                placeholder="https://www.youtube.com/watch?v=...",
                key="youtube_url",
                label_visibility="collapsed"
            )
            
            col_yt1, col_yt2 = st.columns([3, 1])
            with col_yt1:
                download_youtube = st.button("📥 Download & Process", key="download_yt_btn", use_container_width=True)
            
            if download_youtube and youtube_url:
                with st.spinner("⏳ Downloading YouTube video..."):
                    try:
                        fetched = save_from_url(youtube_url)
                        if fetched:
                            st.session_state.video_path = fetched
                            st.session_state.video_processed = False
                            st.success("✅ YouTube video downloaded successfully!")
                        else:
                            st.error(
                                "❌ Failed to download YouTube video.\n\n"
                                "**Common causes:**\n"
                                "• **Video restricted**: Check if video is private, age-restricted, or geo-blocked\n"
                                "• **HLS-only streams**: Some videos don't offer downloadable formats\n"
                                "• **Streaming format issue**: SABR or HLS-only formats aren't fully supported\n\n"
                                "**Solutions:**\n"
                                "1. Try a different video\n"
                                "2. Upload a local MP4 file instead (Local File tab)\n"
                                "3. Check if video is available in your region\n"
                                "4. For age-restricted videos, try using a different video source\n\n"
                                "📝 **Tip**: Download videos locally and upload the MP4 for best results."
                            )
                            
                            # Show troubleshooting tip
                            with st.expander("🔧 Troubleshooting YouTube Downloads"):
                                st.markdown("""
                                **Why YouTube downloads fail:**
                                - YouTube frequently changes its streaming format
                                - Some videos use HLS (HTTP Live Streaming) which requires special handling
                                - Age-restricted content needs authentication
                                - Geographic restrictions vary by region
                                
                                **Best approach for reliable analysis:**
                                1. Download the video directly from YouTube using a desktop tool
                                2. Upload the MP4 file to Video Brain using the "Local File" tab
                                3. This ensures complete, uncompressed video analysis
                                
                                **Supported video sources:**
                                - Local MP4/video files (most reliable)
                                - Direct video URLs (HTTP/HTTPS links to MP4)
                                - Some YouTube videos (quality varies)
                                """)
                    except Exception as e:
                        st.error(f"❌ Error downloading video: {str(e)[:100]}")
                        with st.expander("📋 Technical Details"):
                            st.code(str(e))
        
        # Tab 3: Direct URL
        with upload_tabs[2]:
            st.markdown("**Enter a direct MP4 or video URL:**")
            video_url = st.text_input(
                "Video URL",
                placeholder="https://example.com/video.mp4",
                key="video_url",
                label_visibility="collapsed"
            )
            
            col_url1, col_url2 = st.columns([3, 1])
            with col_url1:
                fetch_url = st.button("🔗 Fetch URL", key="fetch_url_btn", use_container_width=True)
            
            if fetch_url and video_url:
                with st.spinner("⏳ Fetching video..."):
                    try:
                        fetched = save_from_url(video_url)
                        if fetched:
                            st.session_state.video_path = fetched
                            st.session_state.video_processed = False
                            st.success("✅ Video fetched and saved!")
                        else:
                            st.error("❌ Could not fetch the provided URL.")
                    except Exception as e:
                        st.error(f"❌ Error fetching video: {str(e)[:100]}")

    # Column 2: Preview and Processing
    with col2:
        st.markdown("### 👁️ Preview")
        
        # Video preview
        if "video_path" in st.session_state and st.session_state.video_path:
            video_to_show = st.session_state.video_path
            try:
                if isinstance(video_to_show, str) and (
                    video_to_show.startswith("http://") or video_to_show.startswith("https://")
                ):
                    st.video(video_to_show)
                else:
                    with open(video_to_show, "rb") as f:
                        st.video(f.read())
            except Exception:
                st.warning("⚠️ Could not preview the video file.")

            # Process video if not already done
            if not st.session_state.video_processed:
                st.markdown("### ⚙️ Processing Video...")
                
                # Create three stages of processing
                status_placeholder = st.empty()
                timing_placeholder = st.empty()
                timings = {}
                
                # Stage 1: Extract frames
                with st.spinner("📸 Extracting key frames..."):
                    try:
                        start = time.time()
                        frame_extractor = backend.get_frame_extractor(num_frames=5)
                        frames_data = frame_extractor.extract_frame_descriptions(video_to_show)
                        elapsed = time.time() - start
                        timings['frames'] = elapsed
                        
                        st.session_state.frames_data = frames_data if frames_data else None
                        status_placeholder.info(f"✅ Extracted {len(frames_data) if frames_data else 0} frames ({elapsed:.1f}s)")
                    except Exception as e:
                        st.warning(f"⚠️ Frame extraction failed: {e}")
                        st.session_state.frames_data = None
                
                # Stage 2: Extract and transcribe audio
                with st.spinner("🎙️ Extracting and transcribing audio..."):
                    try:
                        start = time.time()
                        transcript = backend.extract_transcript(video_to_show)
                        elapsed = time.time() - start
                        timings['transcript'] = elapsed
                        
                        st.session_state.transcript = transcript
                        if transcript:
                            msg = f"✅ Transcription complete ({len(transcript)} chars, {elapsed:.1f}s)"
                            if elapsed < 5:
                                msg += " 🚀 [cached]"
                            status_placeholder.info(msg)
                        else:
                            st.warning(
                                "⚠️ **Transcription unavailable** - This may be due to:\n"
                                "• No audio track in video\n"
                                "• FFmpeg not installed (audio extraction requires FFmpeg)\n"
                                "• Audio encoding not supported\n\n"
                                "The summary will be based on visual frame analysis instead."
                            )
                            status_placeholder.warning("⚠️ Transcription failed - using frame analysis only")
                    except Exception as e:
                        st.warning(f"⚠️ Transcription failed: {e}")
                        st.session_state.transcript = None
                        status_placeholder.warning("⚠️ Transcription failed - using frame analysis only")
                
                # Stage 3: Generate summary
                with st.spinner("✍️ Generating summary..."):
                    try:
                        start = time.time()
                        session_id = st.session_state.get("session_id") or str(int(time.time()))
                        st.session_state.session_id = session_id
                        
                        summary_result = backend.summarize_video(
                            session_id,
                            video_to_show,
                            transcript=st.session_state.transcript
                        )
                        elapsed = time.time() - start
                        timings['summary'] = elapsed
                        
                        st.session_state.summary = summary_result.get("text")
                        
                        # Store video details for use in Q&A
                        if summary_result.get("video_details"):
                            st.session_state.video_details = summary_result.get("video_details")
                            logger.info(f"Stored video details: {st.session_state.video_details.get('content_type')}")
                        
                        if summary_result.get("error"):
                            st.error(f"❌ Error: {summary_result.get('error')}")
                        else:
                            total = sum(timings.values())
                            timing_msg = f"✅ Processing complete! Total: {total:.1f}s"
                            status_placeholder.success(timing_msg)
                    except Exception as e:
                        st.error(f"❌ Summary generation failed: {e}")
                
                st.session_state.video_processed = True
            
            # Display summary
            if "summary" in st.session_state and st.session_state.summary:
                st.markdown("### 📝 Summary")
                
                # Show what sources were used
                if st.session_state.get("transcript"):
                    st.info("✅ Summary based on video transcript + visual analysis")
                else:
                    st.warning("⚠️ Summary based on visual frame analysis only (no audio transcript available)")
                
                st.write(st.session_state.summary)
                
                # Show diagnostic information in expander
                with st.expander("🔍 **Debug Info** - What was extracted from the video"):
                    try:
                        from utils.diagnostics import diagnose_video_analysis
                        
                        diagnostic_report = diagnose_video_analysis(
                            video_to_show,
                            st.session_state.get("frames_data", []),
                            st.session_state.get("transcript", "")
                        )
                        
                        st.markdown("#### Frame Analysis")
                        frame_count = diagnostic_report['frames']['count']
                        st.text(f"📸 Frames extracted: {frame_count}")
                        
                        if diagnostic_report['frames']['text_snippets']:
                            st.text("📖 Text recognized in frames:")
                            for snippet in diagnostic_report['frames']['text_snippets'][:3]:
                                st.caption(f"• {snippet}")
                        
                        if diagnostic_report['frames']['visual_features']:
                            st.text("👁️ Visual features:")
                            for feature in diagnostic_report['frames']['visual_features'][:2]:
                                st.caption(feature[:150])
                        
                        st.markdown("#### Transcript Analysis")
                        transcript_avail = diagnostic_report['transcript']['available']
                        transcript_len = diagnostic_report['transcript']['length']
                        st.text(f"🎙️ Transcript available: {'✅ Yes' if transcript_avail else '❌ No'}")
                        
                        if transcript_avail:
                            st.text(f"Length: {transcript_len} characters")
                            preview = diagnostic_report['transcript']['preview']
                            if preview:
                                st.caption(f"Preview: {preview}")
                        
                        st.markdown("#### Data Quality Assessment")
                        quality = diagnostic_report['analysis_quality']
                        if quality['sufficient_data']:
                            st.success("✅ **Good data coverage** - Summary should be accurate")
                        else:
                            st.warning("⚠️ **Limited data** - Summary may be incomplete")
                        
                    except Exception as e:
                        st.warning(f"⚠️ Could not generate diagnostic info: {e}")

    # Column 3: Chat Interface
    with col3:
        st.markdown("### 💬 Chat")
        
        if "video_path" not in st.session_state or not st.session_state.video_processed:
            st.info("Upload a video and wait for processing to start chatting.")
        else:
            # Chat input
            user_input = st.chat_input("Ask about the video...")
            
            if user_input:
                # Add user message to chat history
                st.session_state.chat_history.append({
                    "role": "user",
                    "content": user_input
                })
                
                # Generate response
                session_id = st.session_state.get("session_id", str(int(time.time())))
                with st.spinner("🤖 Thinking..."):
                    try:
                        response = backend.handle_user_message(
                            session_id,
                            user_input,
                            video_path=st.session_state.get("video_path"),
                            transcript=st.session_state.get("transcript"),
                            video_details=st.session_state.get("video_details"),
                        )
                        
                        # Add assistant response to chat history
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response.get("text", "No response generated")
                        })
                        
                        if response.get("error"):
                            st.error(f"Error: {response.get('error')}")
                    except Exception as e:
                        st.error(f"Failed to generate response: {e}")
            
            # Display chat history
            st.markdown("### Conversation")
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f"**You:** {msg['content']}")
                else:
                    st.markdown(f"**Assistant:** {msg['content']}")


if __name__ == "__main__":
    main()
