#!/usr/bin/env python3
"""Minimal test script for Riva TTS to debug the 'bad argument type' error."""

import os
import sys

def test_riva_tts():
    """Test Riva TTS with minimal setup."""

    # Import Riva client
    try:
        import riva.client
        from riva.client.proto.riva_tts_pb2 import SynthesizeSpeechRequest
        from riva.client.proto.riva_audio_pb2 import AudioEncoding
        print("✓ Riva client imports successful")
    except ImportError as e:
        print(f"✗ Failed to import Riva client: {e}")
        sys.exit(1)

    # Configuration
    riva_server_url = os.getenv("RIVA_SERVER_URL", "grpc.nvcf.nvidia.com:443")
    api_key = os.getenv("NVIDIA_API_KEY")
    function_id = os.getenv("RIVA_FUNCTION_ID", "877104f7-e885-42b9-8de8-f6e4c6303969")

    # Test with an emotion voice
    voice_name = "Magpie-Multilingual.EN-US.Mia.Happy"
    text = "Hello! This is a test of Riva text to speech with emotion."

    print(f"\nConfiguration:")
    print(f"  Server: {riva_server_url}")
    print(f"  API Key: {'***' + api_key[-4:] if api_key else 'NOT SET'}")
    print(f"  Function ID: {function_id if function_id else 'NOT SET'}")
    print(f"  Voice: {voice_name}")
    print(f"  Text: {text}")

    if not api_key:
        print("\n✗ NVIDIA_API_KEY not set. Please set it:")
        print("  export NVIDIA_API_KEY='your-key-here'")
        sys.exit(1)

    # Build Auth
    print("\n1. Creating Auth...")
    try:
        auth = riva.client.Auth(
            uri=riva_server_url,
            use_ssl=True,
            ssl_cert=None,
        )
        metadata = [("authorization", f"Bearer {api_key}")]
        if function_id:
            metadata.insert(0, ("function-id", function_id))
        auth.metadata = metadata
        print("✓ Auth created")
    except Exception as e:
        print(f"✗ Failed to create Auth: {e}")
        sys.exit(1)

    # Create TTS service
    print("\n2. Creating SpeechSynthesisService...")
    try:
        tts_service = riva.client.SpeechSynthesisService(auth)
        print("✓ TTS service created")
    except Exception as e:
        print(f"✗ Failed to create TTS service: {e}")
        sys.exit(1)

    # Call synthesize using high-level API (not request object)
    # Test the emotion voice directly
    print("\n3. Testing emotion voice...")

    print(f"\n  Trying voice='{voice_name}', lang='en-US'...")
    try:
        response = tts_service.synthesize(
            text=text,
            voice_name=voice_name,
            language_code="en-US",
            encoding=AudioEncoding.LINEAR_PCM,
            sample_rate_hz=22050
        )

        # Check response type
        print(f"    Response type: {type(response)}")

        # Handle both streaming and non-streaming responses
        audio_data = None
        if hasattr(response, 'audio'):
            # Non-streaming response
            if response.audio:
                print(f"    ✓ SUCCESS! Got audio data: {len(response.audio)} bytes")
                audio_data = response.audio
        else:
            # Try as iterator (streaming response)
            try:
                audio_chunks = []
                for resp in response:
                    if hasattr(resp, 'audio') and resp.audio:
                        audio_chunks.append(resp.audio)
                if audio_chunks:
                    audio_data = b''.join(audio_chunks)
                    print(f"    ✓ SUCCESS! Got audio data: {len(audio_data)} bytes (streaming)")
            except TypeError as te:
                print(f"    ✗ Response not iterable: {te}")

        if not audio_data:
            print("    ✗ No audio data received")
            sys.exit(1)

    except Exception as e:
        error_msg = str(e)
        print(f"    ✗ Error: {error_msg}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(f"\n4. Converting PCM to WAV and saving...")
    import wave
    import io

    output_file = "/tmp/riva_test_emotion_output.wav"
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(22050)
        wav_file.writeframes(audio_data)

    with open(output_file, 'wb') as f:
        f.write(wav_buffer.getvalue())

    print(f"✓ Audio saved to {output_file}")
    print(f"\nPlay with: afplay {output_file}")
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_riva_tts()
