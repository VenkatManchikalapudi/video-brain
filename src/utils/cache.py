"""Caching utilities for Video Brain.

Provides file-based caching for expensive operations like frame extraction
and audio transcription to avoid reprocessing the same videos.
"""

import json
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, Any, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class FileCache:
    """Simple file-based cache for storing results of expensive operations."""
    
    def __init__(self, cache_dir: str = ".cache"):
        """Initialize cache with directory."""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Cache initialized at: {self.cache_dir}")
    
    def _get_cache_key(self, video_path: str, operation: str) -> str:
        """Generate a unique cache key based on video file and operation type.
        
        Uses file path and modification time to ensure cache invalidation
        when source file changes.
        
        Args:
            video_path: Path to the video file
            operation: Name of the operation (e.g., 'frames', 'transcript')
            
        Returns:
            Unique cache key string
        """
        try:
            # Get file stats
            stat = os.stat(video_path)
            file_info = f"{video_path}:{stat.st_size}:{stat.st_mtime}"
            
            # Create hash
            hash_obj = hashlib.md5(file_info.encode())
            file_hash = hash_obj.hexdigest()
            
            return f"{operation}_{file_hash}"
        except Exception as e:
            logger.warning(f"Could not generate cache key: {e}")
            return None
    
    def get(self, video_path: str, operation: str) -> Optional[Any]:
        """Retrieve cached result if it exists.
        
        Args:
            video_path: Path to the video file
            operation: Name of the operation
            
        Returns:
            Cached result or None if not found
        """
        try:
            cache_key = self._get_cache_key(video_path, operation)
            if not cache_key:
                return None
            
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    logger.debug(f"Cache hit for {operation} on {Path(video_path).name}")
                    return data.get('result')
        except Exception as e:
            logger.debug(f"Cache retrieval failed: {e}")
        
        return None
    
    def set(self, video_path: str, operation: str, result: Any) -> bool:
        """Store result in cache.
        
        Args:
            video_path: Path to the video file
            operation: Name of the operation
            result: Result to cache
            
        Returns:
            True if cached successfully, False otherwise
        """
        try:
            cache_key = self._get_cache_key(video_path, operation)
            if not cache_key:
                return False
            
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            with open(cache_file, 'w') as f:
                json.dump({
                    'result': result,
                    'video_path': video_path,
                    'operation': operation
                }, f)
            
            logger.debug(f"Cached {operation} for {Path(video_path).name}")
            return True
        except Exception as e:
            logger.warning(f"Cache storage failed: {e}")
            return False
    
    def clear(self) -> int:
        """Clear all cached files.
        
        Returns:
            Number of files removed
        """
        try:
            files = list(self.cache_dir.glob("*.json"))
            for f in files:
                f.unlink()
            logger.info(f"Cache cleared: {len(files)} files removed")
            return len(files)
        except Exception as e:
            logger.error(f"Cache clearing failed: {e}")
            return 0


# Global cache instance
_cache: Optional[FileCache] = None


def get_cache() -> FileCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = FileCache()
    return _cache


def cached(operation: str, skip_cache: bool = False):
    """Decorator to cache function results based on video file.
    
    Caches results of expensive operations. Automatically invalidates
    cache when source video file changes.
    
    Works with both regular functions and instance methods.
    
    Args:
        operation: Name of the operation for cache key
        skip_cache: If True, bypass cache (useful for forcing refresh)
        
    Usage with function:
        @cached('frames')
        def extract_frames(video_path):
            ...
    
    Usage with method:
        @cached('frames')
        def extract_frames(self, video_path):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Determine if this is a method call or function call
            if len(args) > 0 and hasattr(args[0], '__dict__') and not isinstance(args[0], str):
                # Instance method: self is first arg
                self_obj = args[0]
                video_path = args[1] if len(args) > 1 else kwargs.get('video_path')
                remaining_args = args[2:]
            else:
                # Regular function: video_path is first arg
                self_obj = None
                video_path = args[0] if len(args) > 0 else kwargs.get('video_path')
                remaining_args = args[1:] if len(args) > 1 else ()
            
            # Check for skip_cache param
            if kwargs.pop('skip_cache', skip_cache):
                logger.debug(f"Skipping cache for {operation}")
                if self_obj is not None:
                    return func(self_obj, video_path, *remaining_args, **kwargs)
                else:
                    return func(video_path, *remaining_args, **kwargs)
            
            # Try to get from cache
            cache = get_cache()
            cached_result = cache.get(video_path, operation)
            
            if cached_result is not None:
                logger.info(f"Using cached {operation} for video")
                return cached_result
            
            # Compute and cache result
            logger.debug(f"Computing {operation} (not in cache)")
            if self_obj is not None:
                result = func(self_obj, video_path, *remaining_args, **kwargs)
            else:
                result = func(video_path, *remaining_args, **kwargs)
            
            # Store in cache
            cache.set(video_path, operation, result)
            
            return result
        
        return wrapper
    
    return decorator


def clear_cache() -> None:
    """Clear all cached data."""
    cache = get_cache()
    cache.clear()
