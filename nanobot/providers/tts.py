"""TTS Provider abstraction layer for Nanobot."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import asyncio
from dataclasses import dataclass
from loguru import logger

@dataclass
class TTSConfig:
    """Configuration for TTS settings."""
    enabled: bool = False
    provider: str = "edge"  # "edge", "openai", or "riva"
    voice: str = "en-US-AriaNeural"
    rate: str = "+0%"
    pitch: str = "+0%"
    volume: str = "+0%"
    # Additional provider-specific settings
    openai_model: str = "tts-1"  # For OpenAI TTS
    openai_quality: str = "low"  # For OpenAI TTS
    openai_speed: float = 1.0  # For OpenAI TTS
    # NVIDIA Riva specific settings
    riva_server_url: str = "localhost:50051"  # Default Riva server URL
    riva_ssl_cert: str = ""  # SSL certificate path for Riva
    riva_use_ssl: bool = False  # Whether to use SSL for Riva
    riva_function_id: str = ""  # Function ID for NVCF Riva services
    riva_api_key: Optional[str] = None  # API key for NVIDIA Cloud Functions
    openai_api_key: Optional[str] = None  # API key for OpenAI TTS

class BaseTTSProvider(ABC):
    """Abstract base class for TTS providers."""
    
    def __init__(self, config: TTSConfig):
        self.config = config
    
    @abstractmethod
    async def generate_audio(self, text: str) -> Optional[bytes]:
        """Generate audio bytes from text."""
        pass
    
    @abstractmethod
    async def get_supported_voices(self) -> Dict[str, Any]:
        """Get list of supported voices for this provider."""
        pass

# Placeholder for actual implementations
class EdgeTTSProvider(BaseTTSProvider):
    """Edge TTS provider using edge-tts library."""
    
    def __init__(self, config: TTSConfig):
        super().__init__(config)
        self._edge_tts = None
    
    async def generate_audio(self, text: str) -> Optional[bytes]:
        """Generate audio using Edge TTS."""
        if not text.strip():
            return None

        if self._edge_tts is None:
            try:
                import edge_tts
                self._edge_tts = edge_tts
            except ImportError:
                raise ImportError("edge-tts package is required for EdgeTTSProvider. Install with: pip install edge-tts")

        try:
            # edge-tts requires volume in % format e.g. "+0%", not "+0dB"
            volume = self.config.volume
            if volume.endswith("dB"):
                volume = "+0%"

            communicate = self._edge_tts.Communicate(
                text,
                self.config.voice,
                rate=self.config.rate,
                pitch=self.config.pitch,
                volume=volume
            )
            
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            
            if not audio_chunks:
                return None
                
            audio_data = b"".join(audio_chunks)
            return audio_data
        except Exception as e:
            logger.error(f"Error generating audio with Edge TTS: {e}", exc_info=True)
            return None
            
        try:
            # Create communicate object with the specified voice and settings
            communicate = self.edge_tts.Communicate(
                text,
                self.config.voice,
                rate=self.config.rate,
                pitch=self.config.pitch,
                volume=self.config.volume
            )
            
            # Collect audio chunks in memory
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            
            if not audio_chunks:
                return None
                
            # Concatenate all audio chunks
            audio_data = b"".join(audio_chunks)
            return audio_data
        except Exception as e:
            print(f"Error generating audio with EdgeTTS: {e}")
            return None
    
    async def get_supported_voices(self) -> Dict[str, Any]:
        """Get list of supported voices for Edge TTS."""
        try:
            # Actually fetch voices from the service
            voices = await self.edge_tts.list_voices()
            return {
                "voices": [
                    {
                        "name": voice["ShortName"],
                        "locale": voice["Locale"],
                        "gender": voice.get("Gender", "Unknown"),
                        "friendly_name": voice.get("FriendlyName", ""),
                        "style_list": voice.get("StyleList", []),
                    }
                    for voice in voices
                ]
            }
        except Exception as e:
            print(f"Error getting voices from EdgeTTS: {e}")
            return {"voices": []}

class OpenAITTSProvider(BaseTTSProvider):
    """OpenAI TTS provider using OpenAI API."""
    
    def __init__(self, config: TTSConfig):
        super().__init__(config)
        self._openai = None
    
    async def generate_audio(self, text: str) -> Optional[bytes]:
        """Generate audio using OpenAI TTS API."""
        if not text.strip():
            return None
        
        # Get API key from config, fallback to environment variable
        import os
        api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            print("OpenAI TTS: No API key provided in config or environment")
            return None
            
        try:
            # Configure OpenAI client
            client = self.openai.AsyncOpenAI(api_key=api_key)
            
            # Call OpenAI TTS API
            response = await client.audio.speech.create(
                model=self.config.openai_model,
                voice=self.config.voice,
                input=text,
                speed=self.config.openai_speed
            )
            
            # Return audio bytes
            return response.content
        except Exception as e:
            logger.error(f"Error generating audio with OpenAI TTS: {e}", exc_info=True)
            return None
    
    async def get_supported_voices(self) -> Dict[str, Any]:
        """Get list of supported voices for OpenAI TTS."""
        try:
            # OpenAI has fixed voices
            return {
                "voices": [
                    {"name": "alloy", "locale": "en-US", "gender": "Male"},
                    {"name": "echo", "locale": "en-US", "gender": "Male"},
                    {"name": "fable", "locale": "en-US", "gender": "Male"},
                    {"name": "onyx", "locale": "en-US", "gender": "Male"},
                    {"name": "nova", "locale": "en-US", "gender": "Female"},
                    {"name": "shimmer", "locale": "en-US", "gender": "Female"},
                ]
            }
        except Exception as e:
            print(f"Error getting voices from OpenAI TTS: {e}")
            return {"voices": []}


class RivaTTSProvider(BaseTTSProvider):
    """NVIDIA Riva TTS provider using Riva client library."""
    
    def __init__(self, config: TTSConfig):
        super().__init__(config)
        self._riva_client = None
    
    async def generate_audio(self, text: str) -> Optional[bytes]:
        """Generate audio using NVIDIA Riva TTS."""
        if not text.strip():
            return None
            
        if self._riva_client is None:
            try:
                import riva.client
                self._riva_client = riva.client
            except ImportError:
                raise ImportError("nvidia-riva-client package is required for RivaTTSProvider. Install with: pip install nvidia-riva-client")
        
        try:
            # Get API key from config, fallback to environment
            import os
            api_key = self.config.riva_api_key or os.getenv("NVIDIA_API_KEY") or ""

            # Build Auth — metadata must be set as attribute, not constructor kwarg
            if api_key:
                auth = self._riva_client.Auth(
                    uri=self.config.riva_server_url,
                    use_ssl=True,
                    ssl_cert=self.config.riva_ssl_cert if self.config.riva_ssl_cert else None,
                )
                metadata = [("authorization", f"Bearer {api_key}")]
                if self.config.riva_function_id:
                    metadata.insert(0, ("function-id", self.config.riva_function_id))
                auth.metadata = metadata
            else:
                auth = self._riva_client.Auth(
                    uri=self.config.riva_server_url,
                    use_ssl=self.config.riva_use_ssl,
                    ssl_cert=self.config.riva_ssl_cert if self.config.riva_ssl_cert else None,
                )
            
            # Create TTS service
            tts_service = self._riva_client.SpeechSynthesisService(auth)
            
            # Configure synthesis request
            req = self._riva_client.SynthesizeSpeechRequest()
            req.text = text
            req.language_code = self._get_language_code_from_voice()
            req.voice_name = self.config.voice
            
            # Set audio parameters
            req.encoding = self._riva_client.AudioEncoding.LINEAR_PCM
            req.sample_rate_hz = 22050
            
            # Generate speech
            resp = tts_service.synthesize(req)
            
            # Convert PCM to WAV format
            import wave
            import io
            
            # Create WAV file in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(22050)
                wav_file.writeframes(resp.audio)
            
            return wav_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error generating audio with NVIDIA Riva TTS: {e}", exc_info=True)
            return None
    
    def _get_language_code_from_voice(self) -> str:
        """Extract language code from voice name."""
        # Simple heuristic: extract language code from voice name
        # e.g., "en-US" from "en-US-Wavenet-A"
        if "-" in self.config.voice:
            parts = self.config.voice.split("-")
            if len(parts) >= 2:
                return f"{parts[0]}-{parts[1]}"
        return "en-US"  # Default
    
    async def get_supported_voices(self) -> Dict[str, Any]:
        """Get list of supported voices for NVIDIA Riva TTS."""
        try:
            if self._riva_client is None:
                try:
                    import riva.client
                    self._riva_client = riva.client
                except ImportError:
                    return {"voices": []}

            import os
            api_key = self.config.riva_api_key or os.getenv("NVIDIA_API_KEY") or ""

            # Build auth — metadata must be set as attribute, not constructor kwarg
            if api_key:
                auth = self._riva_client.Auth(
                    uri=self.config.riva_server_url,
                    use_ssl=True,
                    ssl_cert=self.config.riva_ssl_cert if self.config.riva_ssl_cert else None,
                )
                metadata = [("authorization", f"Bearer {api_key}")]
                if self.config.riva_function_id:
                    metadata.insert(0, ("function-id", self.config.riva_function_id))
                auth.metadata = metadata
            else:
                auth = self._riva_client.Auth(
                    uri=self.config.riva_server_url,
                    use_ssl=self.config.riva_use_ssl,
                    ssl_cert=self.config.riva_ssl_cert if self.config.riva_ssl_cert else None,
                )
            tts_service = self._riva_client.SpeechSynthesisService(auth)

            voices_response = tts_service.list_voices()

            voices = []
            for voice in voices_response.voices:
                voices.append({
                    "name": voice.name,
                    "locale": voice.language_code,
                    "gender": voice.ssml_gender.name if hasattr(voice, "ssml_gender") else "Unknown",
                    "sample_rate": getattr(voice, "natural_sample_rate_hz", 22050),
                })

            return {"voices": voices}

        except Exception as e:
            logger.warning(f"Could not fetch Riva voices from server ({e}), using fallback list")
            return {
                "voices": [
                    {"name": "English-US-Female-1", "locale": "en-US", "gender": "Female", "sample_rate": 22050},
                    {"name": "English-US-Male-1", "locale": "en-US", "gender": "Male", "sample_rate": 22050},
                    {"name": "English-UK-Female-1", "locale": "en-GB", "gender": "Female", "sample_rate": 22050},
                    {"name": "English-UK-Male-1", "locale": "en-GB", "gender": "Male", "sample_rate": 22050},
                ]
            }