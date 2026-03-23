# Video Brain — Local LLM Video Analysis

A minimal Streamlit frontend for analyzing video content using Ollama, a local LLM inference engine. This application allows you to:

- Upload local MP4 videos or provide direct URLs
- View video previews with metadata (duration, FPS, dimensions)
- Ask questions about video content using a locally-run language model
- Get summaries and insights based on visual frame analysis

**Note**: This app uses visual feature analysis (brightness, color, content patterns) rather than computer vision.
Summaries and answers are based on inferred patterns from key frames, not actual semantic understanding of objects or text.
For best results, use with moderately complex videos where visual patterns are sufficient context.

## Quick Start

### Prerequisites

1. **Ollama** (for local LLM inference)
   - Install from: https://ollama.ai
   - After installation, pull a model: `ollama pull llama3.2:latest`
   - Start Ollama in a separate terminal: `ollama serve`

2. **Tesseract OCR** (for text extraction from video frames)
   - **macOS**: `brew install tesseract`
   - **Linux**: `apt-get install tesseract-ocr`
   - **Windows**: Download from https://github.com/UB-Mannheim/tesseract/wiki

3. **Python 3.9+**

### Setup Instructions

1. Clone or navigate to the repository:

```bash
cd "Video Brain"
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file (optional, for custom configuration):

```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest
OLLAMA_TIMEOUT=300
DEBUG=False
```

5. Ensure Ollama is running in a separate terminal:

```bash
ollama serve
```

6. Run the Streamlit app:

```bash
streamlit run src/streamlit_app.py
```

The app will be available at `http://localhost:8501`

## Project Structure

```
src/
├── __init__.py                      # Package initialization
├── streamlit_app.py                 # Streamlit UI
├── backend.py                       # Backend orchestration
├── config/
│   └── __init__.py                 # Configuration management
├── models/
│   └── __init__.py                 # Data models
├── services/
│   ├── __init__.py
│   ├── ollama_client.py            # Ollama API integration
│   ├── session_manager.py          # Conversation history
│   └── video_processor.py          # Video metadata extraction
└── utils/
    ├── __init__.py
    └── storage.py                   # File upload/download utilities
```

## Configuration

Environment variables (optional):

| Variable          | Default                  | Description                   |
| ----------------- | ------------------------ | ----------------------------- |
| `OLLAMA_HOST`     | `http://localhost:11434` | Ollama API endpoint           |
| `OLLAMA_MODEL`    | `llama3.2:latest`        | LLM model to use              |
| `OLLAMA_TIMEOUT`  | `300`                    | Request timeout in seconds    |
| `TEMP_UPLOAD_DIR` | `temp_uploads`           | Directory for temporary files |
| `DEBUG`           | `False`                  | Enable debug logging          |

## Supported Models

Popular Ollama models (pull with `ollama pull <model>`):

- `llama3.2:latest` - Meta's Llama 3.2 3B (recommended, fast, good quality)
- `llama2` - Meta's Llama 2 7B (larger, more capable but slower)
- `neural-chat` - Intel's Neural Chat (7B, optimized)
- `mistral` - Mistral 7B (faster inference)
- `dolphin-mixtral` - Dolphin Mixtral (8x7B, expert mixer)

Find more at: https://ollama.ai/library

## Requirements

### System Requirements

- **Ollama** — Local LLM inference engine
- **Tesseract** — OCR engine for text extraction
  - macOS: `brew install tesseract`
  - Linux: `apt-get install tesseract-ocr`
  - Windows: https://github.com/UB-Mannheim/tesseract/wiki

### Python Dependencies

- **streamlit** ≥ 1.28.0 — Web framework
- **requests** ≥ 2.31.0 — HTTP client for Ollama API
- **moviepy** ≥ 1.0.3 — Video processing
- **pytesseract** ≥ 0.3.10 — Python OCR interface to Tesseract
- **pillow** ≥ 9.0.0 — Image processing
- **python-dotenv** ≥ 1.0.0 — Environment configuration
- **yt-dlp** ≥ 2023.11.16 — YouTube download support (optional)

See [requirements.txt](requirements.txt) for full list.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system architecture, component descriptions, and data flow diagrams.

## How Video Analysis Works

The app analyzes videos using **optical character recognition (OCR) text extraction** combined with visual analysis:

### Analysis Pipeline

1. **Frame Extraction**: 5 key frames are extracted at evenly-spaced intervals from the video
2. **OCR Text Extraction** (primary): Each frame is scanned for visible text using Tesseract OCR
   - Extracts text from presentations, code, documents, UI, subtitles, captions, annotations
   - Works best with clear, readable text
   - Handles multiple fonts and sizes
3. **Visual Feature Analysis** (fallback): If OCR extracts no text, frames are analyzed for:
   - Lighting conditions (brightness levels)
   - Scene complexity (edge density, contours)
   - Content density (high-contrast, low-contrast)
4. **Frame Descriptions**: Extracted text or visual features are converted to descriptions:
   - **With OCR**: "Text visible: 'Python Tutorial - Variables and Data Types'"
   - **Without OCR**: "Frame shows: bright, text/UI-heavy"
5. **LLM Processing**: These descriptions are passed to Llama which generates summaries and answers

### Content Understanding

- **Best results**: Videos with readable text (presentations, tutorials, code walkthroughs, lectures, webinars)
- **Good results**: Videos with distinct visual patterns (screen recordings, UI demonstrations)
- **Limited results**: Videos with minimal text (movies, vlogs, scenic footage)

**Why this works**: Text content is a strong signal of what a video contains. Even without understanding images semantically, extracted text provides the LLM with accurate information about the video's topic.

### OCR Dependencies

Requires Tesseract OCR engine:

- **macOS**: `brew install tesseract`
- **Linux**: `apt-get install tesseract-ocr` or `yum install tesseract`
- **Windows**: Download from https://github.com/UB-Mannheim/tesseract/wiki

The `pytesseract` Python package bridges the gap between Python and Tesseract.

## Notes for Production

For production deployments, consider:

1. **Persistent Storage** — Replace in-memory session manager with a database (PostgreSQL, MongoDB, Redis)
2. **Scalable Architecture** — Use a task queue (Celery, RQ) for video processing
3. **Cloud Storage** — Store uploads in S3, GCS, or similar instead of local disk
4. **Authentication** — Add user authentication and authorization
5. **Load Balancing** — Deploy Ollama inference on separate GPU-enabled servers
6. **Monitoring** — Add metrics collection and alerting
7. **Error Handling** — Implement comprehensive logging and error tracking

## Troubleshooting

### "Ollama is not available"

Ensure Ollama is running:

```bash
ollama serve
```

Check connectivity:

```bash
curl http://localhost:11434/api/tags
```

### Slow responses

- **Reduce model size**: Use smaller models like `neural-chat` or `mistral`
- **GPU acceleration**: Ensure Ollama is using GPU (check Ollama docs)
- **Increase timeout**: Set `OLLAMA_TIMEOUT` to a higher value

### Out of memory

- Use a smaller model
- Close other applications
- Increase your system's available RAM

## License

[Specify your license here]
