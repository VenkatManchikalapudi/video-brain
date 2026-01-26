"""
Test script for Gemini Video connectivity.
Reads GEMINI_API_KEY from the environment and tests the modular client logic.
"""

import json
import os
import sys
from src import gemini_client as gc

def main():
    # 1. Health Check
    print("--- 🩺 Checking Gemini Health ---")
    try:
        health_status = gc.gemini_health()
        print(f"gemini_health: {health_status}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return

    # 2. Path Validation
    # Tip: Use an absolute path or ensure the file exists relative to where you run the script
    video_path = "path/to/your/actual_video.mp4" 
    
    if not os.path.exists(video_path):
        print(f"⚠️ Warning: Could not find video at '{video_path}'")
        print("Please update video_path in this script with a real file to test summarization.")
        sys.exit(1)

    # 3. Generate Response
    print(f"\n--- 🎥 Requesting Summary for: {os.path.basename(video_path)} ---")
    try:
        # Note: Your gc.generate_response must handle file.upload() 
        # AND polling for state.name == "ACTIVE" internally.
        resp = gc.generate_response(video_path, "Give a 2-line summary.", [])
        
        print("\n--- 🤖 Gemini API Response ---")
        print(json.dumps(resp, indent=2))
        
    except Exception as e:
        print(f"❌ Summarization failed: {e}")

if __name__ == "__main__":
    main()