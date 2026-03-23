"""Diagnostic tools for Video Brain.

Provides detailed analysis of what's happening in the video processing pipeline.
"""

import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


def diagnose_video_analysis(
    video_path: str,
    frames_data: Optional[List[dict]],
    transcript: Optional[str],
) -> Dict[str, any]:
    """Generate diagnostic report on video analysis results.
    
    Shows what data was extracted and identifies potential issues.
    
    Args:
        video_path: Path to the video
        frames_data: Extracted frame information
        transcript: Extracted transcript
        
    Returns:
        Dictionary with diagnostic information
    """
    report = {
        "video": str(video_path),
        "frames": {
            "count": len(frames_data) if frames_data else 0,
            "has_text": False,
            "text_snippets": [],
            "visual_features": [],
        },
        "transcript": {
            "available": transcript is not None and len(transcript.strip()) > 0,
            "length": len(transcript) if transcript else 0,
            "preview": (transcript[:200] + "...") if transcript and len(transcript) > 200 else transcript,
        },
        "analysis_quality": {
            "has_transcript": transcript and len(transcript.strip()) > 10,
            "has_readable_frames": False,
            "sufficient_data": False,
        }
    }
    
    # Analyze frames
    if frames_data:
        for frame in frames_data:
            desc = frame.get('description', '')
            if 'Text visible' in desc:
                report["frames"]["has_text"] = True
                # Extract the text portion
                if '"' in desc:
                    text = desc.split('"')[1]
                    report["frames"]["text_snippets"].append(text[:100])
            elif 'Frame shows' in desc:
                report["frames"]["visual_features"].append(desc)
        
        report["analysis_quality"]["has_readable_frames"] = bool(
            report["frames"]["text_snippets"] or report["frames"]["visual_features"]
        )
    
    # Overall quality assessment
    has_transcript = report["transcript"]["available"]
    has_readable_frames = report["analysis_quality"]["has_readable_frames"]
    
    report["analysis_quality"]["sufficient_data"] = has_transcript or has_readable_frames
    
    # Log summary
    logger.info("=" * 70)
    logger.info("VIDEO ANALYSIS DIAGNOSTIC REPORT")
    logger.info("=" * 70)
    logger.info(f"Video: {video_path}")
    logger.info(f"Frames extracted: {report['frames']['count']}")
    logger.info(f"Transcript available: {report['transcript']['available']} ({report['transcript']['length']} chars)")
    logger.info(f"Frames with readable content: {report['analysis_quality']['has_readable_frames']}")
    logger.info(f"Overall data quality: {'✅ GOOD' if report['analysis_quality']['sufficient_data'] else '⚠️  LIMITED'}")
    logger.info("=" * 70)
    
    if report["frames"]["text_snippets"]:
        logger.info("OCR Text found in frames:")
        for snippet in report["frames"]["text_snippets"][:3]:
            logger.info(f"  - {snippet}")
    
    if report["frames"]["visual_features"]:
        logger.info("Visual features analyzed:")
        for feature in report["frames"]["visual_features"][:3]:
            logger.info(f"  - {feature}")
    
    if transcript:
        logger.info(f"Transcript preview: {report['transcript']['preview']}")
    
    logger.info("=" * 70)
    
    return report


def log_prompt_sent_to_llm(prompt: str) -> None:
    """Log the complete prompt being sent to the LLM for debugging.
    
    Useful for understanding why summaries are inaccurate.
    
    Args:
        prompt: The full prompt string
    """
    logger.debug("=" * 80)
    logger.debug("PROMPT SENT TO OLLAMA LLM")
    logger.debug("=" * 80)
    logger.debug(prompt)
    logger.debug("=" * 80)
