import os
import time
import traceback
from typing import Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv
from pytube import YouTube
import tempfile

def _get_config():
    load_dotenv()  # Ensure .env is loaded each time
    return {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    }

def _download_youtube_video(youtube_url: str) -> str:
    """Download a YouTube video and return the local file path."""
    yt = YouTube(youtube_url)
    video_stream = yt.streams.filter(progressive=True, file_extension="mp4").first()
    if not video_stream:
        raise ValueError("No suitable video stream found for download.")

    temp_dir = tempfile.gettempdir()
    output_path = video_stream.download(output_path=temp_dir)
    return output_path

def generate_response(video_path: str, user_message: str, history: List[Dict]) -> Dict:
    """Uploads video, waits for processing, and returns AI response."""
    config = _get_config()
    
    if not config["api_key"]:
        return {"text": "Error: API Key missing", "segments": [], "error": "GEMINI_API_KEY not set"}

    try:
        if video_path.startswith("https://www.youtube.com") or video_path.startswith("https://youtu.be"):
            try:
                print("Downloading YouTube video...")
                video_path = _download_youtube_video(video_path)
                print(f"Video downloaded to: {video_path}")
            except Exception as e:
                return {
                    "text": "",
                    "segments": [],
                    "error": f"Failed to download YouTube video: {e}"
                }

        genai.configure(api_key=config["api_key"])
        model = genai.GenerativeModel(model_name=config["model"])

        # 1. UPLOAD VIDEO
        # This is the step your previous code was missing
        video_file = genai.upload_file(path=video_path)
        
        # 2. POLL UNTIL ACTIVE
        # Gemini needs to 'index' the video before it can answer questions
        while video_file.state.name == "PROCESSING":
            time.sleep(3)
            video_file = genai.get_file(video_file.name)
        
        if video_file.state.name == "FAILED":
            raise RuntimeError("Video processing failed on Google's servers.")

        # 3. GENERATE CONTENT
        prompt = [
            "You are a video expert. Answer based on the video provided.",
            "Always provide timestamps in [MM:SS] format.",
            video_file, 
            user_message
        ]
        
        response = model.generate_content(prompt)
        
        return {
            "text": response.text,
            "segments": [], # You can add regex here to parse timestamps later
            "error": None
        }

    except Exception:
        return {
            "text": "Fallback: AI call failed.",
            "segments": [],
            "error": traceback.format_exc()
        }

def is_gemini_available() -> bool:
    config = _get_config()
    return bool(config["api_key"])

def gemini_health() -> Dict:
    config = _get_config()
    if not config["api_key"]:
        return {"available": False, "reason": "GEMINI_API_KEY missing"}
    return {"available": True, "reason": f"Ready with {config['model']}"}