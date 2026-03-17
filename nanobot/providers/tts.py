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
    riva_server_url: str = "grpc.nvcf.nvidia.com:443"  # Default NVCF server URL
    riva_ssl_cert: str = ""  # SSL certificate path for Riva
    riva_use_ssl: bool = True  # Whether to use SSL for Riva (default True for NVCF)
    riva_function_id: str = "877104f7-e885-42b9-8de8-f6e4c6303969"  # Function ID for NVCF Riva services
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
    
    async def get_supported_voices(self) -> Dict[str, Any]:
        """Get list of supported voices for Edge TTS."""
        try:
            if self._edge_tts is None:
                import edge_tts
                self._edge_tts = edge_tts
            
            # Actually fetch voices from the service
            voices = await self._edge_tts.list_voices()
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
            logger.error(f"Error getting voices from EdgeTTS: {e}")
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
        
        import os
        api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            logger.error("OpenAI TTS: No API key provided in config or environment")
            return None
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=api_key)
            
            response = await client.audio.speech.create(
                model=self.config.openai_model,
                voice=self.config.voice,
                input=text,
                speed=self.config.openai_speed
            )
            
            if hasattr(response, 'content'):
                logger.debug("OpenAI TTS returned audio content")
                return response.content
            else:
                logger.error(f"OpenAI response missing .content → {type(response)}")
                return None
                
        except Exception as e:
            logger.exception("OpenAI TTS generation failed")
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
            logger.error(f"Error getting voices from OpenAI TTS: {e}")
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

            # Import AudioEncoding enum
            from riva.client.proto.riva_audio_pb2 import AudioEncoding

            # Get language code from voice name
            language_code = self._get_language_code_from_voice()

            # Generate speech using the high-level API
            # The synthesize() method takes parameters directly, not a request object
            # Riva has a 400 char limit per request, so chunk if needed
            MAX_CHUNK = 390
            if len(text) > MAX_CHUNK:
                # Split text into chunks at sentence boundaries
                chunks = self._split_text(text, MAX_CHUNK)
                logger.debug(f"Text too long ({len(text)} chars), split into {len(chunks)} chunks")
            else:
                chunks = [text]

            all_audio = []
            for i, chunk in enumerate(chunks):
                logger.debug(f"Calling Riva synthesize chunk {i+1}/{len(chunks)}: text={chunk[:50]}..., voice={self.config.voice}, lang={language_code}")

                response = tts_service.synthesize(
                    text=chunk,
                    voice_name=self.config.voice,
                    language_code=language_code,
                    encoding=AudioEncoding.LINEAR_PCM,
                    sample_rate_hz=22050
                )

                if hasattr(response, 'audio') and response.audio:
                    all_audio.append(response.audio)
                else:
                    # Streaming response
                    for resp in response:
                        if hasattr(resp, 'audio') and resp.audio:
                            all_audio.append(resp.audio)

            if not all_audio:
                logger.error("No audio data received from Riva TTS service")
                return None

            audio_data = b''.join(all_audio)
            logger.debug(f"Received {len(audio_data)} bytes of audio data")
            
            # Convert PCM to WAV format
            import wave
            import io
            
            # Create WAV file in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(22050)
                wav_file.writeframes(audio_data)
            
            return wav_buffer.getvalue()
            
        except Exception as e:
            logger.error("Error generating audio with NVIDIA Riva TTS: " + str(e).replace("{", "{{").replace("}", "}}"), exc_info=True)
            return None
    
    @staticmethod
    def _split_text(text: str, max_len: int) -> list[str]:
        """Split text into chunks at sentence boundaries."""
        chunks = []
        while len(text) > max_len:
            # Find last sentence boundary within limit
            cut = max_len
            for sep in ['. ', '! ', '? ', '; ', ', ', ' ']:
                idx = text.rfind(sep, 0, max_len)
                if idx > 0:
                    cut = idx + len(sep)
                    break
            chunks.append(text[:cut].strip())
            text = text[cut:].strip()
        if text:
            chunks.append(text)
        return chunks

    def _get_language_code_from_voice(self) -> str:
        """Extract language code from voice name."""
        voice = self.config.voice

        # For Magpie voices, extract the locale part after the first dot
        if "Magpie-Multilingual." in voice:
            # "Magpie-Multilingual.EN-US.Mia.Happy" -> "EN-US"
            after_prefix = voice.split("Magpie-Multilingual.", 1)[1]
            parts = after_prefix.split(".")
            if len(parts) >= 2:
                # parts[0] = "EN-US", convert to "en-US"
                locale = parts[0]  # e.g. "EN-US"
                locale_parts = locale.split("-")
                if len(locale_parts) == 2:
                    return f"{locale_parts[0].lower()}-{locale_parts[1].upper()}"
                return locale

        # Map common language names to codes
        lang_map = {
            "English": "en",
            "Spanish": "es",
            "French": "fr",
            "German": "de",
            "Italian": "it",
            "Portuguese": "pt",
            "Chinese": "zh",
            "Japanese": "ja",
            "Korean": "ko",
        }

        # Try to extract from voice name
        if "-" in voice or "." in voice:
            # Split by both - and .
            parts = voice.replace(".", "-").split("-")
            if len(parts) >= 2:
                lang = parts[0]
                region = parts[1]

                # If first part is a full language name, map it
                if lang in lang_map:
                    lang = lang_map[lang]

                # Ensure region is uppercase (US, GB, etc.)
                region = region.upper()

                return f"{lang}-{region}"

        return "en-US"  # Default
    
    async def get_supported_voices(self) -> Dict[str, Any]:
        """Get list of supported voices for NVIDIA Riva TTS."""
        try:
            if self._riva_client is None:
                import riva.client
                self._riva_client = riva.client

            import os
            api_key = self.config.riva_api_key or os.getenv("NVIDIA_API_KEY") or ""

            # Build auth
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

            # Get config from server
            from riva.client.proto.riva_tts_pb2 import RivaSynthesisConfigRequest
            config_req = RivaSynthesisConfigRequest()
            config_response = tts_service.stub.GetRivaSynthesisConfig(
                config_req,
                metadata=auth.get_auth_metadata()
            )

            # Parse subvoices from model config
            voices = []
            voice_prefix = self.config.riva_server_url.split(':')[0].replace('grpc.', '').replace('.nvidia.com', '')
            if voice_prefix == 'nvcf':
                voice_prefix = "Magpie-Multilingual"

            for model_config in config_response.model_config:
                for param_key, param_value in model_config.parameters.items():
                    if param_key == "subvoices":
                        # Parse subvoices string: "EN-US.Aria:11,EN-US.Mia.Happy:4,..."
                        for voice_entry in param_value.split(','):
                            if ':' in voice_entry:
                                voice_name, voice_id = voice_entry.split(':', 1)
                                # Extract locale and name parts
                                # Format: "EN-US.Mia.Happy" or "EN-US.Aria"
                                parts = voice_name.split('.')
                                if len(parts) >= 2:
                                    locale = parts[0]  # e.g., "EN-US"
                                    base_name = parts[1]  # e.g., "Mia", "Aria"
                                    emotion = parts[2] if len(parts) >= 3 else None  # e.g., "Happy", "Calm"

                                    # Determine gender from common name patterns
                                    gender = "Unknown"
                                    if base_name in ["Aria", "Mia", "Sofia", "Isabela", "Louise", "Phung"]:
                                        gender = "Female"
                                    elif base_name in ["Jason", "Leo", "Ray", "Diego", "Pascal", "HouZhen", "Siwei", "Long"]:
                                        gender = "Male"

                                    # Build full voice name in Magpie format
                                    full_voice_name = f"{voice_prefix}.{voice_name}"

                                    # Build display name with emotion if present
                                    display_name = base_name
                                    if emotion:
                                        display_name = f"{base_name} ({emotion})"

                                    voices.append({
                                        "name": full_voice_name,
                                        "locale": locale.lower(),
                                        "gender": gender,
                                        "sample_rate": 22050,
                                        "display_name": display_name,
                                        "emotion": emotion,
                                    })

            if voices:
                return {"voices": voices}

        except Exception as e:
            logger.warning(f"Could not fetch Riva voices from server: {e}")

        # Fallback to hardcoded list
        return {
            "voices": [
                {"name": "Magpie-Multilingual.EN-US.Aria", "locale": "en-us", "gender": "Female", "sample_rate": 22050},
                {"name": "Magpie-Multilingual.EN-US.Mia", "locale": "en-us", "gender": "Female", "sample_rate": 22050},
                {"name": "Magpie-Multilingual.EN-US.Jason", "locale": "en-us", "gender": "Male", "sample_rate": 22050},
                {"name": "Magpie-Multilingual.EN-US.Leo", "locale": "en-us", "gender": "Male", "sample_rate": 22050},
            ]
        }