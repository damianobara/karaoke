#!/usr/bin/env python3
"""
Audio FX Live - Minimalist Real-time Audio Processing
MVP: Pass-through + Delay Effect + Waveform Visualization + CLI Controls
"""

import argparse
import sounddevice as sd
import sys
import threading
import time
import matplotlib.pyplot as plt
from core.engine import AudioEngine
from effects.delay import SimpleDelay
from visualizers.waveform import WaveformVisualizer
from visualizers.spectrogram import SpectrogramVisualizer


def list_devices():
    """List available audio devices."""
    devices = sd.query_devices()
    print("\n[Audio Devices]")
    print("-" * 80)
    for i, device in enumerate(devices):
        print(f"{i:2d}: {device['name']}")
        print(f"    Input channels:  {device['max_input_channels']}")
        print(f"    Output channels: {device['max_output_channels']}")
    print()


def print_controls():
    """Print available controls."""
    print("\n[Controls]")
    print("  e - Toggle delay effect")
    print("  w - Increase wet (echo effect amount)")
    print("  d - Decrease wet (less echo effect)")
    print("  f - Increase feedback")
    print("  g - Decrease feedback")
    print("  v - Toggle visualization")
    print("  s - Show effect status")
    print("  q - Quit")
    print()


def run_interactive(input_device: int, output_device: int, buffer_size: int, with_visualizer: bool, visualizer_type: str = "waveform"):
    """Run interactive pass-through with effects and controls."""
    engine = AudioEngine(
        buffer_size=buffer_size,
        sample_rate=48000,
        input_device=input_device,
        output_device=output_device,
        channels=2,
    )

    # Create delay effect
    delay = SimpleDelay(
        delay_ms=200,
        feedback=0.4,
        wet=0.3,
        sample_rate=48000,
    )

    # Create visualizer
    viz = None
    viz_thread = None
    if with_visualizer:
        if visualizer_type == "spectrogram":
            viz = SpectrogramVisualizer(sample_rate=48000, name="Spectrogram")
        else:
            viz = WaveformVisualizer(sample_rate=48000, name="Waveform")
        engine.add_visualizer(viz)

    engine.start()
    engine.add_effect(delay)

    print("\n[Pass-through + Effects Mode]")
    print_controls()

    # Start visualizer if enabled
    if viz:
        viz_thread = viz.start_threaded()
        print("[OK] Visualizer started")
        print()

    try:
        status_interval = 0
        while True:
            try:
                # Non-blocking input check
                cmd = input("[cmd] ").strip().lower()

                if cmd == "q":
                    print("[Quit] Exiting...")
                    break

                elif cmd == "e":
                    delay.toggle()
                    state = "ON" if delay.enabled else "OFF"
                    print(f"[+] Delay effect: {state}")

                elif cmd == "w":
                    new_wet = min(delay.wet + 0.1, 1.0)
                    delay.set_wet(new_wet)
                    print(f"[+] Wet: {new_wet:.1f}")

                elif cmd == "d":
                    new_wet = max(delay.wet - 0.1, 0.0)
                    delay.set_wet(new_wet)
                    print(f"[-] Wet: {new_wet:.1f}")

                elif cmd == "f":
                    new_fb = min(delay.feedback + 0.05, 0.95)
                    delay.set_feedback(new_fb)
                    print(f"[+] Feedback: {new_fb:.2f}")

                elif cmd == "g":
                    new_fb = max(delay.feedback - 0.05, 0.0)
                    delay.set_feedback(new_fb)
                    print(f"[-] Feedback: {new_fb:.2f}")

                elif cmd == "v":
                    if viz:
                        print("[!] Visualizer already running (close window to stop)")
                    else:
                        print("[!] Visualizer not enabled (use --with-viz flag)")

                elif cmd == "s":
                    print("\n[Status]")
                    print(f"   Latency: {engine.latency_ms:.1f}ms")
                    print(f"   Effects: {', '.join(engine.list_effects())}")
                    print(f"   Delay wet: {delay.wet:.2f}")
                    print(f"   Delay feedback: {delay.feedback:.2f}")
                    print()

                elif cmd == "?":
                    print_controls()

                else:
                    if cmd and cmd not in ["", " "]:
                        print("[!] Unknown command. Press '?' for help")

            except EOFError:
                # Stdin closed - exit gracefully
                break

    except KeyboardInterrupt:
        print("\n[Interrupt] Stopping...")

    finally:
        engine.stop()
        if viz:
            viz.stop_and_wait(timeout=2.0)
        if viz_thread is not None and viz_thread.is_alive():
            viz_thread.join(timeout=2.0)
        plt.close('all')  # Clean up matplotlib figures


def main():
    parser = argparse.ArgumentParser(
        description="Audio FX Live - Real-time audio processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --list-devices
  python main.py --input 1 --output 3 --buffer 512
  python main.py --input -1 --output -1 --with-viz
  python main.py --with-viz --viz-type spectrogram
  python main.py  # Uses default devices, no visualization
        """,
    )

    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit",
    )
    parser.add_argument(
        "--input", type=int, default=-1, help="Input device index (-1 = default)"
    )
    parser.add_argument(
        "--output", type=int, default=-1, help="Output device index (-1 = default)"
    )
    parser.add_argument(
        "--buffer", type=int, default=512, help="Buffer size in samples (default: 512)"
    )
    parser.add_argument(
        "--with-viz",
        action="store_true",
        help="Enable visualization",
    )
    parser.add_argument(
        "--viz-type",
        type=str,
        default="waveform",
        choices=["waveform", "spectrogram"],
        help="Visualizer type: waveform or spectrogram (default: waveform)",
    )

    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        sys.exit(0)

    # Run interactive mode
    input_dev = None if args.input == -1 else args.input
    output_dev = None if args.output == -1 else args.output

    run_interactive(input_dev, output_dev, args.buffer, args.with_viz, args.viz_type)


if __name__ == "__main__":
    main()
