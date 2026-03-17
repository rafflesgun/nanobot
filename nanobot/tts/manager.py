"""TTS Manager for handling text-to-speech generation."""

from typing import Optional
from loguru import logger

from nanobot.config.schema import TTSConfig
from nanobot.providers.tts import BaseTTSProvider, EdgeTTSProvider, OpenAITTSProvider, RivaTTSProvider, TTSConfig as ProviderTTSConfig



class TTSManager:
    """Manager for TTS operations with multiple providers."""
    
    def __init__(self, config: TTSConfig):
        self.config = config
        self._provider: Optional[BaseTTSProvider] = None
    
    def _get_provider(self) -> Optional[BaseTTSProvider]:
        """Get the configured TTS provider."""
        # Check if we need to recreate the provider due to configuration change
        if self._provider is not None:
            # Compare current provider type with config
            current_provider_type = type(self._provider).__name__
            expected_provider_type = {
                "edge": "EdgeTTSProvider",
                "openai": "OpenAITTSProvider", 
                "riva": "RivaTTSProvider"
            }.get(self.config.provider, None)
            
            if current_provider_type != expected_provider_type:
                logger.debug(f"Configuration changed: {current_provider_type} -> {expected_provider_type}, recreating provider")
                self._provider = None
        
        if self._provider is None:
            # Convert schema TTSConfig to provider TTSConfig
            provider_config = ProviderTTSConfig(
                enabled=self.config.enabled,
                provider=self.config.provider,
                voice=self.config.voice,
                rate=self.config.rate,
                pitch=self.config.pitch,
                volume=self.config.volume,
                openai_model=self.config.openai_model,
                openai_quality=self.config.openai_quality,
                openai_speed=self.config.openai_speed,
                openai_api_key=self.config.openai_api_key,
                riva_server_url=self.config.riva_server_url,
                riva_use_ssl=self.config.riva_use_ssl,
                riva_ssl_cert=self.config.riva_ssl_cert,
                riva_function_id=self.config.riva_function_id or "",
                riva_api_key=self.config.riva_api_key,
            )
            
            try:
                if self.config.provider == "edge":
                    self._provider = EdgeTTSProvider(provider_config)
                elif self.config.provider == "openai":
                    # API key is now read inside OpenAITTSProvider from config
                    self._provider = OpenAITTSProvider(provider_config)
                elif self.config.provider == "riva":
                    # API key is now read inside RivaTTSProvider from config
                    self._provider = RivaTTSProvider(provider_config)
                else:
                    logger.error(f"Unknown TTS provider: {self.config.provider}")
                    return None
            except ImportError as e:
                logger.error(f"Failed to initialize TTS provider {self.config.provider}: {e}")
                return None
            except Exception as e:
                logger.error(f"Error initializing TTS provider: {e}")
                return None
        
        return self._provider
    
    async def generate_voice_note(self, text: str) -> Optional[bytes]:
        """
        Generate voice note audio in OGG/Opus format for Telegram.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            OGG/Opus audio bytes or None if generation fails
        """
        logger.debug(f"TTS generate_voice_note called with config: enabled={self.config.enabled}, provider={self.config.provider}, voice={self.config.voice}")
        
        if not self.config.enabled:
            logger.debug("TTS is not enabled in config")
            return None
            
        provider = self._get_provider()
        if not provider:
            logger.error("Failed to get TTS provider")
            return None
        
        try:
            # Lazy import audio utilities only when actually generating voice
            from nanobot.utils.audio import convert_to_ogg_opus, get_audio_duration

            # Generate audio using the provider
            logger.info(f"Generating TTS audio with {self.config.provider} provider, voice: {self.config.voice}")
            audio_bytes = await provider.generate_audio(text)
            
            if not audio_bytes:
                logger.warning("TTS provider returned no audio data")
                return None
            
            # Convert to OGG/Opus format for Telegram
            if self.config.provider == "edge":
                # Edge TTS returns MP3
                ogg_bytes = await convert_to_ogg_opus(audio_bytes, input_format="mp3")
            elif self.config.provider == "openai":
                # OpenAI TTS returns MP3 by default
                ogg_bytes = await convert_to_ogg_opus(audio_bytes, input_format="mp3")
            elif self.config.provider == "riva":
                # Riva TTS returns WAV
                ogg_bytes = await convert_to_ogg_opus(audio_bytes, input_format="wav")
            else:
                logger.error(f"Unknown provider format for {self.config.provider}")
                return None
            
            if not ogg_bytes:
                logger.warning("Audio conversion to OGG/Opus failed")
                return None
            
            # Log duration for monitoring
            duration = await get_audio_duration(ogg_bytes, input_format="ogg")
            logger.info(f"TTS generated successfully: {duration:.1f}s")
            
            return ogg_bytes
            
        except Exception as e:
            logger.error(f"TTS generation failed: {e}", exc_info=True)
            return None
    
    async def get_supported_voices(self, provider: str | None = None) -> dict:
        """Get supported voices from the current or specified provider."""
        if provider and provider != self.config.provider:
            # Build a temporary provider instance for the requested provider
            # Inherit all settings from current config, only change the provider
            from nanobot.providers.tts import EdgeTTSProvider, RivaTTSProvider, OpenAITTSProvider, TTSConfig as ProviderTTSConfig
            tmp_config = ProviderTTSConfig(
                provider=provider,
                voice=self.config.voice,
                rate=self.config.rate,
                pitch=self.config.pitch,
                volume=self.config.volume,
                openai_model=self.config.openai_model,
                openai_quality=self.config.openai_quality,
                openai_speed=self.config.openai_speed,
                openai_api_key=self.config.openai_api_key,
                riva_server_url=self.config.riva_server_url,
                riva_use_ssl=self.config.riva_use_ssl,
                riva_ssl_cert=self.config.riva_ssl_cert or "",
                riva_function_id=self.config.riva_function_id or "",
                riva_api_key=self.config.riva_api_key,
            )
            try:
                if provider == "edge":
                    tmp_provider = EdgeTTSProvider(tmp_config)
                elif provider == "riva":
                    tmp_provider = RivaTTSProvider(tmp_config)
                elif provider == "openai":
                    tmp_provider = OpenAITTSProvider(tmp_config)
                else:
                    return {"voices": []}
                return await tmp_provider.get_supported_voices()
            except Exception as e:
                logger.error(f"Failed to get voices for provider {provider}: {e}")
                return {"voices": []}

        p = self._get_provider()
        if not p:
            return {"voices": []}
        try:
            return await p.get_supported_voices()
        except Exception as e:
            logger.error(f"Failed to get supported voices: {e}")
            return {"voices": []}