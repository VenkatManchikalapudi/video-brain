"""Helpers for saving uploaded files to a temporary local directory.

This module provides a single convenience function `save_temp_file`
which writes the uploaded file object provided by Streamlit to a
`temp_uploads/` directory located at the repository root and returns
the absolute path to the saved file.

Notes:
- For production use consider storing uploads in cloud storage
  (e.g. GCS, S3) and avoid keeping large files on the app server.
"""

import os
import time
from pathlib import Path
from typing import Optional

import requests
try:
    from yt_dlp import YoutubeDL
except Exception:
    YoutubeDL = None


def save_temp_file(uploaded_file) -> str:
    """Save an uploaded Streamlit file to a temporary local folder and return path.

    `uploaded_file` is the object returned by `st.file_uploader`.
    This function attempts to use `getbuffer()` when available for
    efficient writes; otherwise it falls back to `read()`.
    """
    root = Path(__file__).resolve().parents[1]
    temp_dir = root / "temp_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)

    fname = getattr(uploaded_file, "name", None) or f"upload_{int(time.time())}.mp4"
    out_path = temp_dir / fname

    with open(out_path, "wb") as f:
        try:
            f.write(uploaded_file.getbuffer())
        except AttributeError:
            f.write(uploaded_file.read())

    return str(out_path)


def save_from_url(url: str, timeout: int = 30) -> Optional[str]:
    """Download a video from `url` into `temp_uploads` and return the path.

    Returns None on failure. This keeps behavior simple: callers may
    still prefer to stream the URL directly into `st.video` when the
    URL is publicly accessible.
    """
    # If the URL is a YouTube (or similar) page, prefer to resolve a
    # direct media stream URL using yt-dlp so we can pass that to ffmpeg
    # without needing a full download. If yt-dlp isn't available, fall
    # back to attempting a plain HTTP download of the URL.
    try:
        if YoutubeDL is not None and ("youtube.com" in url or "youtu.be" in url):
            try:
                with YoutubeDL({"format": "best", "skip_download": True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    # `info` may include a direct `url` or a list of `formats`.
                    if isinstance(info, dict):
                        if "url" in info:
                            return info["url"]
                        formats = info.get("formats") or []
                        # Prefer highest-resolution format that contains a direct URL.
                        formats_sorted = sorted(
                            formats, key=lambda f: f.get("height") or 0, reverse=True
                        )
                        for f in formats_sorted:
                            if "url" in f:
                                return f["url"]
            except Exception:
                # If yt-dlp fails, continue to the generic downloader below.
                pass

        # Generic HTTP download path (for direct MP4 links).
        root = Path(__file__).resolve().parents[1]
        temp_dir = root / "temp_uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Derive a filename from the URL path or use a timestamped name.
        fname = Path(url).name
        if not fname or "." not in fname:
            fname = f"download_{int(time.time())}.mp4"

        out_path = temp_dir / fname

        # Stream the download to avoid large memory usage.
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        return str(out_path)
    except Exception:
        return None
