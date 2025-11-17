import sounddevice as sd
import numpy as np
import time
from threading import Lock
from typing import List
from core.effect import EffectBase
from core.visualizer import VisualizerBase


class AudioEngine:
    """Real-time audio processing engine.

    - Handles WASAPI stream on Windows
    - Thread-safe effect chain
    - Measures latency and dropouts
    - Non-blocking visualizer integration
    """

    def __init__(
        self,
        buffer_size: int = 512,
        sample_rate: int = 48000,
        input_device: int = None,
        output_device: int = None,
        channels: int = 2,
    ):
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        self.channels = channels
        self.input_device = input_device
        self.output_device = output_device

        # Thread-safe effect chain
        self.effects: List[EffectBase] = []
        self.effect_lock = Lock()

        # Visualizers
        self.visualizers: List[VisualizerBase] = []

        # Stream
        self.stream = None
        self.running = False

        # Metrics
        self.latency_ms = 0
        self.processor_time_ms = 0
        self.total_frames = 0
        self.underruns = 0

    def _audio_callback(self, indata, outdata, frames, time_info, status):
        """WASAPI callback - audio thread (ultra-low latency context).

        - MUST be fast (< 50% buffer time = ~5ms @ 512 samples)
        - ZERO Python loops on samples
        - Only numpy array operations
        """
        start_time = time.perf_counter()

        if status:
            if status.input_overflow or status.output_underflow:
                self.underruns += 1

        # Get input audio
        audio = indata.copy()

        # Apply effects chain (thread-safe)
        with self.effect_lock:
            for effect in self.effects:
                audio = effect(audio)

        # Output
        outdata[:] = audio

        # Send to visualizers (non-blocking, drop if queue full)
        for viz in self.visualizers:
            viz.push_audio(audio)

        # Metrics
        proc_time = (time.perf_counter() - start_time) * 1000
        self.processor_time_ms = proc_time
        self.total_frames += frames

    def start(self):
        """Start audio stream."""
        if self.running:
            return

        # Calculate latency (simplified: device latency + buffer)
        self.latency_ms = (self.buffer_size / self.sample_rate) * 1000 * 2

        print(f"\n[AudioEngine Starting]")
        print(f"   Buffer: {self.buffer_size} samples ({self.latency_ms:.1f}ms latency)")
        print(f"   Sample rate: {self.sample_rate} Hz")
        print(f"   Channels: {self.channels}")

        self.stream = sd.Stream(
            samplerate=self.sample_rate,
            blocksize=self.buffer_size,
            device=(self.input_device, self.output_device),
            channels=self.channels,
            callback=self._audio_callback,
            dtype="float32",
        )

        self.stream.start()
        self.running = True
        print(f"[OK] Stream started (latency: {self.latency_ms:.1f}ms)")

    def stop(self):
        """Stop audio stream."""
        if not self.running:
            return

        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()

        print("\n[Session metrics]")
        print(f"   Total frames: {self.total_frames}")
        print(f"   Underruns: {self.underruns}")
        print(f"   Peak processor time: {self.processor_time_ms:.2f}ms")

    def add_effect(self, effect: EffectBase):
        """Add effect to chain (thread-safe)."""
        with self.effect_lock:
            self.effects.append(effect)
        print(f"[+] Added effect: {effect.name}")

    def remove_effect(self, effect: EffectBase):
        """Remove effect from chain (thread-safe)."""
        with self.effect_lock:
            if effect in self.effects:
                self.effects.remove(effect)
        print(f"[-] Removed effect: {effect.name}")

    def add_visualizer(self, visualizer: VisualizerBase):
        """Add visualizer (non-blocking)."""
        self.visualizers.append(visualizer)
        print(f"[+] Added visualizer: {visualizer.name}")

    def get_effect(self, name: str) -> EffectBase:
        """Get effect by name."""
        with self.effect_lock:
            for effect in self.effects:
                if effect.name == name:
                    return effect
        return None

    def list_effects(self) -> List[str]:
        """List all effects with status."""
        with self.effect_lock:
            return [f"{e.name} ({'ON' if e.enabled else 'OFF'})" for e in self.effects]
