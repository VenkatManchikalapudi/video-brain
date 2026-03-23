"""Video frame extraction and analysis utilities.

Provides functionality to extract key frames from videos and generate
visual descriptions that can be used for AI analysis.
"""

import logging
from typing import Optional, List
from pathlib import Path
from utils.cache import cached

logger = logging.getLogger(__name__)


class FrameExtractor:
    """Extracts and processes key frames from video files."""
    
    def __init__(self, num_frames: int = 5):
        """Initialize frame extractor.
        
        Args:
            num_frames: Number of key frames to extract from video.
                       For TV shows/long videos, this will be increased automatically.
        """
        self.num_frames = num_frames
        self.min_frames = 5
        self.max_frames = 15
    
    def _describe_frame_content(self, image) -> str:
        """Generate a semantic description of frame content with OCR text extraction.
        
        Analyzes image features and extracts visible text to provide meaningful 
        descriptions for the AI model to understand video context.
        
        Args:
            image: PIL Image object
            
        Returns:
            Detailed description including extracted text or visual features
        """
        try:
            import numpy as np
            from PIL import ImageStat
            
            descriptions = []
            
            # Convert to numpy array
            img_array = np.array(image)
            height, width = img_array.shape[:2]
            
            # 1. ATTEMPT OCR TEXT EXTRACTION - PRIMARY SIGNAL FOR CONTENT
            ocr_text = self._extract_text_from_frame(image)
            
            if ocr_text and len(ocr_text.strip()) > 10:  # Minimum text length
                # Clean extracted text
                clean_text = " ".join(ocr_text.split())[:200]
                return f"Text visible: \"{clean_text}\""
            
            # If no valid text detected, use visual features as fallback
            descriptions = []
            
            # 2. VISUAL FEATURES (brightness, color, complexity)
            brightness = np.mean(img_array)
            
            if brightness > 200:
                descriptions.append("very bright")
            elif brightness > 150:
                descriptions.append("bright")
            elif brightness < 50:
                descriptions.append("very dark")
            elif brightness < 100:
                descriptions.append("dark")
            else:
                descriptions.append("normal lighting")
            
            # 3. COLOR DISTRIBUTION - detect if color or grayscale
            if len(img_array.shape) == 3:
                r_mean = np.mean(img_array[:,:,0])
                g_mean = np.mean(img_array[:,:,1])
                b_mean = np.mean(img_array[:,:,2])
                
                color_variance = np.var([r_mean, g_mean, b_mean])
                if color_variance > 500:
                    descriptions.append("colorful")
                else:
                    descriptions.append("grayscale/muted")
                
                # 4. EDGE DENSITY - indicates UI/text presence vs pure imagery
                gray = np.mean(img_array, axis=2)
                edges_h = np.abs(gray[:, 1:] - gray[:, :-1])
                edges_v = np.abs(gray[1:, :] - gray[:-1, :])
                edge_density = (np.mean(edges_h) + np.mean(edges_v)) / 2
                
                if edge_density > 40:
                    descriptions.append("high detail/UI")
                elif edge_density > 20:
                    descriptions.append("textured content")
                else:
                    descriptions.append("smooth/blurred")
            
            # 5. MOTION/BLUR DETECTION via Laplacian variance
            try:
                gray = np.mean(img_array, axis=2) if len(img_array.shape) == 3 else img_array
                laplacian = np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]])
                blur_score = np.var(np.convolve(gray.flatten(), laplacian.flatten()))
                
                if blur_score < 100:
                    descriptions.append("blurred/low motion")
                elif blur_score > 500:
                    descriptions.append("sharp/clear")
            except:
                pass
            
            if descriptions:
                result = "Frame shows: " + ", ".join(descriptions)
            else:
                result = "Video frame content"
            
            return result
            
        except Exception as e:
            logger.warning(f"Frame analysis failed: {e}")
            return "Video frame"
    
    def _extract_text_from_frame(self, image) -> str:
        """Extract visible text from frame using OCR.
        
        Uses pytesseract if available to extract text from the frame.
        This provides the most accurate content signal for video understanding.
        
        Args:
            image: PIL Image object
            
        Returns:
            Extracted text or empty string if OCR unavailable or no text found
        """
        try:
            import pytesseract
            from PIL import ImageEnhance, ImageOps
            import numpy as np
            
            # Create a copy to avoid modifying original
            img = image.copy()
            
            # Convert to grayscale for better OCR
            if img.mode != 'L':
                img = ImageOps.grayscale(img)
            
            # Aggressive contrast enhancement for better text visibility
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(3.0)  # Increased from 2.0
            
            # Brightness adjustment for very dark images
            brightness = np.mean(np.array(img))
            if brightness < 100:
                brightness_enhancer = ImageEnhance.Brightness(img)
                img = brightness_enhancer.enhance(1.5)
            
            # Extract text
            text = pytesseract.image_to_string(img).strip()
            
            # VALIDATE: Filter out garbage/corrupted OCR results
            if not text or len(text) == 0:
                return ""
            
            # Check if result is mostly garbage characters
            # Real text should have reasonable character distribution
            text_lines = text.split('\n')
            valid_lines = []
            
            for line in text_lines:
                if not line.strip():
                    continue
                    
                # Count printable ASCII characters vs total
                printable = sum(1 for c in line if 32 <= ord(c) < 127)
                total = len(line)
                
                if total > 0 and printable / total > 0.7:  # At least 70% valid chars
                    valid_lines.append(line.strip())
            
            if valid_lines:
                return '\n'.join(valid_lines)
            
            return ""
            
        except ImportError:
            logger.debug("pytesseract not available for OCR")
            return ""
        except Exception as e:
            logger.debug(f"OCR extraction failed: {e}")
            return ""
    
    def extract_frame_descriptions(self, video_path: str) -> List[dict]:
        """Extract key frames from video and return frame information.
        
        For TV shows and longer videos, automatically increases frame count
        to capture more meaningful moments.
        
        Args:
            video_path: Path to video file
            
        Returns:
            List of frame dicts with timestamp and description
        """
        try:
            from moviepy import VideoFileClip
            from PIL import Image
            
            clip = VideoFileClip(video_path)
            duration = float(clip.duration)  # Ensure it's a float
            
            # Adaptive frame count based on video duration
            # TV shows/long videos get more frames to capture content variety
            if duration < 60:
                num_frames = self.min_frames  # Short clips: 5 frames
            elif duration < 300:
                num_frames = min(self.max_frames, int(duration / 30))  # ~1 frame per 30s
            else:
                num_frames = self.max_frames  # Long videos: max frames
            
            logger.info(f"Extracting {num_frames} frames from {duration:.1f}s video (adaptive)")
            
            # Calculate evenly spaced frame times
            frame_times = [
                (i + 1) * duration / (num_frames + 1)
                for i in range(num_frames)
            ]
            
            frames_data = []
            
            for idx, t in enumerate(frame_times):
                try:
                    # Get frame at time t
                    frame = clip.get_frame(t)
                    
                    # Convert to PIL Image
                    frame_image = Image.fromarray(frame.astype('uint8'))
                    
                    # Describe the frame content
                    description = self._describe_frame_content(frame_image)
                    
                    # Resize for efficiency
                    frame_image.thumbnail((320, 240), Image.Resampling.LANCZOS)
                    
                    # Format timestamp
                    minutes = int(t) // 60
                    seconds = int(t) % 60
                    timestamp = f"{minutes:02d}:{seconds:02d}"
                    
                    frames_data.append({
                        'timestamp': timestamp,
                        'time_seconds': t,
                        'description': description,
                        'width': frame_image.width,
                        'height': frame_image.height,
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to extract frame at {t}s: {e}")
                    continue
            
            # Clean up
            try:
                clip.close()
            except Exception:
                pass
            
            logger.info(f"Extracted {len(frames_data)} frames from {video_path}")
            return frames_data
            
        except ImportError:
            logger.error("MoviePy not installed; cannot extract frames")
            return []
        except Exception as e:
            logger.error(f"Frame extraction failed: {e}")
            return []
    
    def get_frame_context_prompt(self, frames_data: List[dict]) -> str:
        """Generate a context prompt from extracted frames.
        
        Args:
            frames_data: List of frame dicts from extract_frame_descriptions
            
        Returns:
            Formatted prompt with frame information
        """
        if not frames_data:
            return ""
        
        prompt_parts = [
            "This video contains the following key frames:"
        ]
        
        for frame in frames_data:
            timestamp = frame.get('timestamp', 'unknown')
            description = frame.get('description', 'Frame captured')
            prompt_parts.append(f"\n  • {timestamp}: {description}")
        
        return "\n".join(prompt_parts)


# Singleton instance
_frame_extractor: Optional[FrameExtractor] = None


def get_frame_extractor(num_frames: int = 5) -> FrameExtractor:
    """Get or create the frame extractor singleton."""
    global _frame_extractor
    if _frame_extractor is None:
        _frame_extractor = FrameExtractor(num_frames=num_frames)
    return _frame_extractor
