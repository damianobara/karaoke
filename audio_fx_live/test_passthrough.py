#!/usr/bin/env python3
"""Quick test: verify pass-through audio works."""

import time
from core.engine import AudioEngine

def test_passthrough():
    """Test basic pass-through for 3 seconds."""
    print("\n[Test] Starting 3-second pass-through test...")

    engine = AudioEngine(
        buffer_size=512,
        sample_rate=48000,
        input_device=None,  # Use default
        output_device=None,  # Use default
        channels=2,
    )

    try:
        engine.start()
        print("[Test] Audio should be passing through now...")
        time.sleep(3)
        print("[Test] Test complete!")

    finally:
        engine.stop()

if __name__ == "__main__":
    test_passthrough()
