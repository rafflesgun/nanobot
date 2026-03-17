#!/usr/bin/env python3
"""Test voice parsing from GetRivaSynthesisConfig."""

import asyncio
import os
import sys

async def test_voice_parsing():
    """Test that get_supported_voices correctly parses the config."""

    from nanobot.providers.tts import TTSConfig, RivaTTSProvider

    # Create config
    config = TTSConfig(
        enabled=True,
        provider="riva",
        voice="Magpie-Multilingual.EN-US.Aria",
        riva_server_url=os.getenv("RIVA_SERVER_URL", "grpc.nvcf.nvidia.com:443"),
        riva_use_ssl=True,
        riva_function_id=os.getenv("RIVA_FUNCTION_ID", "877104f7-e885-42b9-8de8-f6e4c6303969"),
        riva_api_key=os.getenv("NVIDIA_API_KEY")
    )

    if not config.riva_api_key:
        print("✗ NVIDIA_API_KEY not set")
        sys.exit(1)

    print("Creating RivaTTSProvider...")
    provider = RivaTTSProvider(config)

    print("\nFetching supported voices...")
    voices_data = await provider.get_supported_voices()

    voices = voices_data.get("voices", [])
    print(f"\n✓ Found {len(voices)} voices\n")

    # Group by locale
    by_locale = {}
    for voice in voices:
        locale = voice["locale"]
        if locale not in by_locale:
            by_locale[locale] = []
        by_locale[locale].append(voice)

    # Display grouped by locale
    for locale in sorted(by_locale.keys()):
        print(f"\n{locale.upper()}:")
        for voice in by_locale[locale]:
            emotion = f" [{voice.get('emotion', 'Neutral')}]" if voice.get('emotion') else ""
            print(f"  {voice['gender']:6} - {voice['name']}{emotion}")

    print(f"\n✅ Voice parsing test completed!")

if __name__ == "__main__":
    asyncio.run(test_voice_parsing())
