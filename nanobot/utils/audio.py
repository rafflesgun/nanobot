"""Audio utilities for Nanobot TTS functionality."""

import warnings

# Suppress pydub SyntaxWarnings about invalid escape sequences BEFORE importing pydub
warnings.filterwarnings(
    "ignore",
    category=SyntaxWarning,
    module="pydub.utils",
)

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
        logger.debug(f"Converting audio from {input_format} to OGG/Opus, input size: {len(audio_bytes)} bytes")
        
        # Load audio from bytes
        audio = AudioSegment.from_file(BytesIO(audio_bytes), format=input_format)
        logger.debug(f"Loaded audio: {len(audio)}ms, {audio.channels} channels, {audio.frame_rate}Hz")
        
        # Convert to mono if stereo (Telegram voice notes work better in mono)
        if audio.channels > 1:
            audio = audio.set_channels(1)
            logger.debug("Converted stereo to mono")
        
        # Set frame rate to 48kHz (recommended for Opus)
        audio = audio.set_frame_rate(48000)
        logger.debug(f"Set frame rate to 48000Hz")
        
        # Export to OGG/Opus format
        ogg_buffer = BytesIO()
        audio.export(
            ogg_buffer,
            format="ogg",
            codec="libopus",
            bitrate=bitrate
        )
        
        ogg_data = ogg_buffer.getvalue()
        logger.debug(f"Conversion successful: {len(ogg_data)} bytes OGG/Opus output")
        return ogg_data
    except Exception as e:
        logger.error(f"Audio conversion failed: {e}")
        logger.exception("Full conversion error details:")
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
        logger.debug(f"Getting duration for {input_format} audio, size: {len(audio_bytes)} bytes")
        audio = AudioSegment.from_file(BytesIO(audio_bytes), format=input_format)
        duration = len(audio) / 1000.0  # pydub returns duration in milliseconds
        logger.debug(f"Audio duration: {duration:.2f}s")
        return duration
    except Exception as e:
        logger.error(f"Could not determine audio duration: {e}")
        logger.exception("Full duration calculation error details:")
        return 0.0