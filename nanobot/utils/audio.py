"""Audio utilities for Nanobot TTS functionality."""

from io import BytesIO
from typing import Optional
import asyncio
from loguru import logger

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False


async def convert_to_ogg_opus(audio_bytes: bytes, input_format: str = "mp3", bitrate: str = "32k") -> Optional[bytes]:
    """
    Convert audio bytes to OGG/Opus format suitable for Telegram voice notes.
    
    Args:
        audio_bytes: Input audio data in specified format
        input_format: Input format (default "mp3", could be "mp3", "wav", "webm", etc.)
        bitrate: Target bitrate for output (default "32k")
        
    Returns:
        OGG/Opus audio bytes or None if conversion fails
    """
    if not PYDUB_AVAILABLE:
        logger.error("pydub not available for audio conversion")
        return None
        
    try:
        # Load audio from bytes
        audio = AudioSegment.from_file(BytesIO(audio_bytes), format=input_format)
        
        # Convert to mono if stereo (Telegram voice notes work better in mono)
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Set frame rate to 48kHz (recommended for Opus)
        audio = audio.set_frame_rate(48000)
        
        # Export to OGG/Opus format
        ogg_buffer = BytesIO()
        audio.export(
            ogg_buffer,
            format="ogg",
            codec="libopus",
            bitrate=bitrate
        )
        
        return ogg_buffer.getvalue()
    except Exception as e:
        logger.error(f"Audio conversion failed: {e}")
        return None


async def get_audio_duration(audio_bytes: bytes, input_format: str = "mp3") -> float:
    """
    Get the duration of audio in seconds.
    
    Args:
        audio_bytes: Audio data
        input_format: Format of the input audio
        
    Returns:
        Duration in seconds or 0.0 if unable to determine
    """
    if not PYDUB_AVAILABLE:
        logger.error("pydub not available for audio duration calculation")
        return 0.0
        
    try:
        audio = AudioSegment.from_file(BytesIO(audio_bytes), format=input_format)
        return len(audio) / 1000.0  # pydub returns duration in milliseconds
    except Exception as e:
        logger.error(f"Could not determine audio duration: {e}")
        return 0.0