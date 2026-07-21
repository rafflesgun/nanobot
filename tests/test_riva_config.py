#!/usr/bin/env python3
"""Test script to fetch Riva TTS configuration including available voices."""

import os
import sys


def test_riva_config():
    """Test fetching Riva TTS configuration."""

    # Import Riva client
    try:
        import riva.client
        from riva.client.proto.riva_tts_pb2 import RivaSynthesisConfigRequest
        print("✓ Riva client imports successful")
    except ImportError as e:
        print(f"✗ Failed to import Riva client: {e}")
        sys.exit(1)

    # Configuration
    riva_server_url = os.getenv("RIVA_SERVER_URL", "grpc.nvcf.nvidia.com:443")
    api_key = os.getenv("NVIDIA_API_KEY")
    function_id = os.getenv("RIVA_FUNCTION_ID", "877104f7-e885-42b9-8de8-f6e4c6303969")

    print("\nConfiguration:")
    print(f"  Server: {riva_server_url}")
    print(f"  API Key: {'***' + api_key[-4:] if api_key else 'NOT SET'}")
    print(f"  Function ID: {function_id if function_id else 'NOT SET'}")

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

    # Try to get config
    print("\n3. Calling GetRivaSynthesisConfig...")
    try:
        # Create empty request
        config_req = RivaSynthesisConfigRequest()

        # Call the RPC directly via stub
        config_response = tts_service.stub.GetRivaSynthesisConfig(
            config_req,
            metadata=auth.get_auth_metadata()
        )

        print(f"✓ Got config response: {type(config_response)}")

        # Use protobuf's ListFields() to safely inspect the message
        print("\nConfig response fields:")
        for field_descriptor, value in config_response.ListFields():
            print(f"  {field_descriptor.name}: {value}")

        # Also try common field names
        print("\nChecking common field names:")
        for field_name in ['model_config', 'voices', 'language_codes', 'sample_rate_hz', 'models']:
            if hasattr(config_response, field_name):
                try:
                    value = getattr(config_response, field_name)
                    print(f"  {field_name}: {value}")
                except Exception as e:
                    print(f"  {field_name}: <error accessing: {e}>")

        # Print the full protobuf message as string
        print("\nFull config response:")
        print(config_response)

    except Exception as e:
        print(f"✗ Failed to get config: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n✅ Config fetch completed!")

if __name__ == "__main__":
    test_riva_config()
