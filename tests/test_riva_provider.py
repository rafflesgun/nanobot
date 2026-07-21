"""Test Riva TTS using the actual nanobot provider and manager classes."""
import asyncio
import os
import sys
import traceback

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from nanobot.providers.tts import RivaTTSProvider, TTSConfig
from nanobot.tts.manager import TTSManager


async def test_provider_directly():
    """Test RivaTTSProvider.generate_audio() directly."""
    print("=" * 60)
    print("TEST 1: RivaTTSProvider.generate_audio() directly")
    print("=" * 60)

    config = TTSConfig(
        enabled=True,
        provider="riva",
        voice="Magpie-Multilingual.EN-US.Mia.Happy",
        riva_api_key=os.getenv("NVIDIA_API_KEY", ""),
        riva_server_url="grpc.nvcf.nvidia.com:443",
        riva_use_ssl=True,
        riva_function_id="877104f7-e885-42b9-8de8-f6e4c6303969",
    )

    print(f"  voice:       {config.voice}")
    print(f"  server:      {config.riva_server_url}")
    print(f"  api_key:     ***{config.riva_api_key[-4:] if config.riva_api_key else 'MISSING'}")
    print(f"  function_id: {config.riva_function_id}")
    print()

    provider = RivaTTSProvider(config)

    try:
        audio = await provider.generate_audio("Hello! This is a test of Riva TTS through the nanobot provider.")
        if audio:
            print(f"  ✓ Got {len(audio)} bytes of audio data")
            # Save to file for verification
            with open("/tmp/test_provider_output.wav", "wb") as f:
                f.write(audio)
            print("  ✓ Saved to /tmp/test_provider_output.wav")
            print("  Play with: afplay /tmp/test_provider_output.wav")
        else:
            print("  ✗ generate_audio() returned None")
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        traceback.print_exc()


async def test_manager():
    """Test TTSManager.generate_voice_note() end-to-end."""
    print()
    print("=" * 60)
    print("TEST 2: TTSManager.generate_voice_note() end-to-end")
    print("=" * 60)

    config = TTSConfig(
        enabled=True,
        provider="riva",
        voice="Magpie-Multilingual.EN-US.Mia.Happy",
        riva_api_key=os.getenv("NVIDIA_API_KEY", ""),
        riva_server_url="grpc.nvcf.nvidia.com:443",
        riva_use_ssl=True,
        riva_function_id="877104f7-e885-42b9-8de8-f6e4c6303969",
    )

    manager = TTSManager(config)

    try:
        ogg_bytes = await manager.generate_voice_note("Hello! This is a test through the TTS manager.")
        if ogg_bytes:
            print(f"  ✓ Got {len(ogg_bytes)} bytes of OGG audio")
            with open("/tmp/test_manager_output.ogg", "wb") as f:
                f.write(ogg_bytes)
            print("  ✓ Saved to /tmp/test_manager_output.ogg")
            print("  Play with: afplay /tmp/test_manager_output.ogg")
        else:
            print("  ✗ generate_voice_note() returned None")
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_provider_directly())
    asyncio.run(test_manager())
