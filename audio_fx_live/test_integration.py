#!/usr/bin/env python3
"""Integration test: verify all components work together."""

import time
import numpy as np
from core.engine import AudioEngine
from effects.delay import SimpleDelay


def test_integration():
    """Test full integration of audio engine and effects."""
    print("\n[Integration Test] Audio FX Live")
    print("=" * 60)

    # Create engine
    print("\n[1] Creating AudioEngine...")
    engine = AudioEngine(
        buffer_size=512,
        sample_rate=48000,
        input_device=None,
        output_device=None,
        channels=2,
    )
    print("[OK] Engine created")

    # Create delay effect
    print("\n[2] Creating SimpleDelay effect...")
    delay = SimpleDelay(
        delay_ms=200,
        feedback=0.4,
        wet=0.3,
        sample_rate=48000,
    )
    print("[OK] Delay effect created")

    # Start engine
    print("\n[3] Starting audio engine...")
    try:
        engine.start()
        print("[OK] Engine started")
        print(f"    Latency: {engine.latency_ms:.1f}ms")
    except Exception as e:
        print(f"[ERROR] Failed to start engine: {e}")
        return False

    # Add effect
    print("\n[4] Adding delay effect to chain...")
    engine.add_effect(delay)
    print("[OK] Delay effect added")

    # Let audio run for 2 seconds
    print("\n[5] Running audio for 2 seconds...")
    try:
        time.sleep(2.0)
        frames = engine.total_frames
        underruns = engine.underruns
        print(f"[OK] Audio ran successfully")
        print(f"    Frames processed: {frames}")
        print(f"    Underruns: {underruns}")
        if underruns > 0:
            print(f"    [WARN] Detected {underruns} underruns")
    except Exception as e:
        print(f"[ERROR] Audio error: {e}")
        engine.stop()
        return False

    # Test effect controls
    print("\n[6] Testing effect controls...")
    try:
        # Toggle effect
        delay.disable()
        print(f"    Effect disabled: {not delay.enabled}")

        delay.enable()
        print(f"    Effect enabled: {delay.enabled}")

        # Adjust wet
        delay.set_wet(0.7)
        print(f"    Wet set to: {delay.wet}")

        # Adjust feedback
        delay.set_feedback(0.6)
        print(f"    Feedback set to: {delay.feedback}")

        print("[OK] All controls working")
    except Exception as e:
        print(f"[ERROR] Control test failed: {e}")
        engine.stop()
        return False

    # Test effect listing
    print("\n[7] Testing effect listing...")
    try:
        effects = engine.list_effects()
        print(f"    Active effects: {effects}")
        print("[OK] Effect listing works")
    except Exception as e:
        print(f"[ERROR] Listing failed: {e}")
        engine.stop()
        return False

    # Stop engine
    print("\n[8] Stopping audio engine...")
    try:
        engine.stop()
        print("[OK] Engine stopped")
    except Exception as e:
        print(f"[ERROR] Stop failed: {e}")
        return False

    # Verify audio processing
    print("\n[9] Verifying audio processing...")
    if frames > 0 and underruns == 0:
        print("[OK] Audio processed without underruns")
        return True
    else:
        print("[WARN] Audio had issues during processing")
        return underruns == 0  # Success if no underruns


def test_effect_chain():
    """Test adding/removing multiple effects."""
    print("\n[Effect Chain Test]")
    print("=" * 60)

    engine = AudioEngine(
        buffer_size=512,
        sample_rate=48000,
    )

    # Create multiple delay instances
    print("\n[1] Creating multiple effects...")
    delay1 = SimpleDelay(delay_ms=200, feedback=0.3, wet=0.3)
    delay2 = SimpleDelay(delay_ms=100, feedback=0.2, wet=0.2)

    engine.start()

    try:
        # Add first effect
        engine.add_effect(delay1)
        time.sleep(0.5)

        # Add second effect
        engine.add_effect(delay2)
        effects = engine.list_effects()
        print(f"    Effects in chain: {effects}")
        assert len(effects) == 2, "Should have 2 effects"

        time.sleep(0.5)

        # Remove one effect
        engine.remove_effect(delay1)
        effects = engine.list_effects()
        print(f"    After removal: {effects}")
        assert len(effects) == 1, "Should have 1 effect left"

        print("[OK] Effect chain operations work")
        return True

    except Exception as e:
        print(f"[ERROR] Chain test failed: {e}")
        return False

    finally:
        engine.stop()


def test_numpy_safety():
    """Test that delay effect handles edge cases."""
    print("\n[NumPy Safety Test]")
    print("=" * 60)

    delay = SimpleDelay(delay_ms=100, feedback=0.5, wet=0.5, sample_rate=48000)

    # Test mono input
    print("\n[1] Testing mono input...")
    mono = np.random.randn(512).astype(np.float32)
    output = delay.process(mono)
    assert output.ndim == 1, "Mono output should be 1D"
    assert len(output) == 512, "Output size should match input"
    print("[OK] Mono input handling works")

    # Test stereo input
    print("\n[2] Testing stereo input...")
    stereo = np.random.randn(512, 2).astype(np.float32)
    output = delay.process(stereo)
    assert output.ndim == 2, "Stereo output should be 2D"
    assert output.shape == (512, 2), "Output shape should match input"
    print("[OK] Stereo input handling works")

    # Test clipping
    print("\n[3] Testing output clipping...")
    loud = np.ones((512, 2), dtype=np.float32) * 10.0  # Very loud input
    output = delay.process(loud)
    assert np.all(output >= -1.0) and np.all(output <= 1.0), "Output should be clipped"
    print("[OK] Output clipping works")

    return True


if __name__ == "__main__":
    success = True

    try:
        success = test_integration() and success
    except Exception as e:
        print(f"\n[FATAL] Integration test crashed: {e}")
        import traceback
        traceback.print_exc()
        success = False

    try:
        success = test_effect_chain() and success
    except Exception as e:
        print(f"\n[FATAL] Effect chain test crashed: {e}")
        import traceback
        traceback.print_exc()
        success = False

    try:
        success = test_numpy_safety() and success
    except Exception as e:
        print(f"\n[FATAL] NumPy safety test crashed: {e}")
        import traceback
        traceback.print_exc()
        success = False

    print("\n" + "=" * 60)
    if success:
        print("[SUCCESS] All integration tests passed!")
    else:
        print("[FAILURE] Some tests failed")

    print()
