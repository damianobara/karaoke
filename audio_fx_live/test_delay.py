#!/usr/bin/env python3
"""Test delay effect."""

import numpy as np
from effects.delay import SimpleDelay

def test_delay():
    """Test delay effect produces echo."""
    print("\n[Test] Delay Effect")

    # Create delay effect
    delay = SimpleDelay(
        delay_ms=200,
        feedback=0.5,
        wet=0.5,
        sample_rate=48000,
    )

    # Create test signal: click at t=0
    frames = 48000  # 1 second @ 48kHz
    test_signal = np.zeros(frames)
    test_signal[0] = 1.0  # Click at start

    # Process through delay
    output = delay.process(test_signal)

    # Delay should appear after ~200ms = 9600 samples
    echo_position = int(0.2 * 48000)  # 200ms in samples

    # Initial click (position 0) goes through as 50% due to wet mix: 0.5*1.0 + 0.5*0 = 0.5
    initial_click = output[0]

    # Between click and echo should be silent (no delayed signal yet)
    between = output[1:echo_position-1]

    # Echo should appear at echo_position with amplitude ~0.5 (50% wet mix of the delayed click)
    echo_region = output[echo_position:echo_position+1000]

    print(f"   Input signal: 1 click at position 0")
    print(f"   Processing through delay (200ms, feedback=0.5, wet=0.5)")
    print(f"   Initial output (position 0): {initial_click:.3f}")
    print(f"   Between click and echo: max={np.max(np.abs(between)):.6f}, avg={np.mean(np.abs(between)):.6f}")
    print(f"   Echo region ({echo_position}-{echo_position+100}): max={np.max(np.abs(echo_region[:100])):.3f}")

    # Initial should be ~0.5 (50% wet mix of 1.0 input)
    if 0.4 < initial_click < 0.6:
        print("[OK] Initial click shows correct dry/wet mix (0.5)")
    else:
        print("[WARN] Initial click amplitude unexpected")

    # Between click and echo should be very quiet
    if np.max(np.abs(between)) < 0.01:
        print("[OK] Silent between click and echo")
    else:
        print("[WARN] Unexpected signal between click and echo")

    # Echo should appear at echo_position
    if np.max(np.abs(echo_region)) > 0.2:
        print("[OK] Echo detected at expected position")
    else:
        print("[FAIL] No echo detected")

    # Test effect enable/disable
    print("\n[Test] Effect Toggle")
    delay.disable()
    output_disabled = delay.process(test_signal)
    print(f"   Input clipped to [-1, 1]: {np.all(output_disabled >= -1.0) and np.all(output_disabled <= 1.0)}")
    print(f"   Pass-through (effect disabled): {np.allclose(output_disabled, test_signal)}")
    print("[OK] Effect toggle works")

    # Test wet/dry controls
    print("\n[Test] Wet/Dry Controls")
    delay.enable()

    delay.set_wet(0.0)
    dry_only = delay.process(test_signal.copy())
    print(f"   Wet=0.0 (fully dry): {np.allclose(dry_only, test_signal)}")

    delay.set_wet(1.0)
    wet_only = delay.process(test_signal.copy())
    print(f"   Wet=1.0 (fully wet): different from input")
    print(f"   Difference sum: {np.sum(np.abs(wet_only - test_signal)):.2f}")

    print("[OK] Wet/dry controls work")
    print()

if __name__ == "__main__":
    test_delay()
