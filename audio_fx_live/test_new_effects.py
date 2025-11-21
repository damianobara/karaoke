#!/usr/bin/env python3
"""Test script for new sound effects: Reverb, Distortion, and Chorus."""

import numpy as np
from effects import SimpleReverb, SimpleDistortion, SimpleChorus


def test_reverb():
    """Test SimpleReverb effect."""
    print("Testing SimpleReverb...")

    # Create effect
    reverb = SimpleReverb(room_size=0.7, damping=0.5, wet=0.3)

    # Generate test signal (1000 samples, stereo)
    test_audio = np.random.randn(1000, 2).astype(np.float32) * 0.1

    # Process audio
    output = reverb.process(test_audio)

    # Verify output
    assert output.shape == test_audio.shape, "Output shape mismatch"
    assert output.dtype == np.float32, "Output dtype mismatch"
    assert np.all(np.abs(output) <= 1.0), "Output exceeds [-1, 1] range"

    print("✓ SimpleReverb test passed")


def test_distortion():
    """Test SimpleDistortion effect."""
    print("Testing SimpleDistortion...")

    # Create effect
    distortion = SimpleDistortion(drive=8.0, tone=0.7, level=0.5)

    # Generate test signal (1000 samples, stereo)
    test_audio = np.random.randn(1000, 2).astype(np.float32) * 0.1

    # Process audio
    output = distortion.process(test_audio)

    # Verify output
    assert output.shape == test_audio.shape, "Output shape mismatch"
    assert output.dtype == np.float32, "Output dtype mismatch"
    assert np.all(np.abs(output) <= 1.0), "Output exceeds [-1, 1] range"

    print("✓ SimpleDistortion test passed")


def test_chorus():
    """Test SimpleChorus effect."""
    print("Testing SimpleChorus...")

    # Create effect
    chorus = SimpleChorus(rate=2.0, depth=0.4, wet=0.5)

    # Generate test signal (1000 samples, stereo)
    test_audio = np.random.randn(1000, 2).astype(np.float32) * 0.1

    # Process audio
    output = chorus.process(test_audio)

    # Verify output
    assert output.shape == test_audio.shape, "Output shape mismatch"
    assert output.dtype == np.float32, "Output dtype mismatch"
    assert np.all(np.abs(output) <= 1.0), "Output exceeds [-1, 1] range"

    print("✓ SimpleChorus test passed")


def test_mono_input():
    """Test all effects with mono input."""
    print("Testing effects with mono input...")

    # Generate mono test signal
    test_audio = np.random.randn(1000).astype(np.float32) * 0.1

    # Test each effect
    reverb = SimpleReverb()
    output_reverb = reverb.process(test_audio)
    assert output_reverb.shape == test_audio.shape, "Reverb mono output shape mismatch"

    distortion = SimpleDistortion()
    output_dist = distortion.process(test_audio)
    assert output_dist.shape == test_audio.shape, "Distortion mono output shape mismatch"

    chorus = SimpleChorus()
    output_chorus = chorus.process(test_audio)
    assert output_chorus.shape == test_audio.shape, "Chorus mono output shape mismatch"

    print("✓ Mono input test passed")


def test_enable_disable():
    """Test enable/disable functionality."""
    print("Testing enable/disable...")

    test_audio = np.random.randn(100, 2).astype(np.float32) * 0.1

    effects = [
        SimpleReverb(),
        SimpleDistortion(),
        SimpleChorus(),
    ]

    for effect in effects:
        # Disable and test
        effect.disable()
        output_disabled = effect(test_audio)
        assert np.allclose(output_disabled, test_audio), f"{effect.name} should pass through when disabled"

        # Enable and test
        effect.enable()
        output_enabled = effect(test_audio)
        # Should NOT be identical to input (effect is applied)
        assert not np.allclose(output_enabled, test_audio), f"{effect.name} should modify audio when enabled"

    print("✓ Enable/disable test passed")


if __name__ == "__main__":
    print("=" * 50)
    print("Running tests for new sound effects")
    print("=" * 50)

    test_reverb()
    test_distortion()
    test_chorus()
    test_mono_input()
    test_enable_disable()

    print("=" * 50)
    print("All tests passed! ✓")
    print("=" * 50)
